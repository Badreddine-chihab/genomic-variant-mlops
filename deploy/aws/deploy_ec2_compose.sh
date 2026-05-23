#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-genopredict}"
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.small}"
VOLUME_SIZE_GB="${VOLUME_SIZE_GB:-30}"
SSH_CIDR="${SSH_CIDR:-}"
APP_CIDR="${APP_CIDR:-0.0.0.0/0}"
KEY_NAME="${KEY_NAME:-${APP_NAME}-ec2-key}"
SG_NAME="${SG_NAME:-${APP_NAME}-compose-sg}"
INSTANCE_NAME="${INSTANCE_NAME:-${APP_NAME}-compose}"
GENERATED_DIR="${GENERATED_DIR:-deploy/aws/generated}"
KEY_PATH="${GENERATED_DIR}/${KEY_NAME}.pem"
ARCHIVE_PATH="${GENERATED_DIR}/${APP_NAME}-bundle.tar.gz"

if ! command -v aws >/dev/null; then
  echo "aws CLI is required." >&2
  exit 1
fi

for bin in ssh scp tar curl; do
  if ! command -v "$bin" >/dev/null; then
    echo "$bin is required." >&2
    exit 1
  fi
done

mkdir -p "$GENERATED_DIR"

if [ -z "$SSH_CIDR" ]; then
  PUBLIC_IP="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  SSH_CIDR="${PUBLIC_IP}/32"
fi

echo "Deploying ${APP_NAME} to AWS region ${AWS_REGION}"
echo "Instance type: ${INSTANCE_TYPE}"
echo "EBS volume: ${VOLUME_SIZE_GB} GiB"
echo "SSH allowed from: ${SSH_CIDR}"
echo "App ports allowed from: ${APP_CIDR}"

CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
echo "AWS account: ${CALLER_ACCOUNT}"

VPC_ID="$(aws ec2 describe-vpcs \
  --region "$AWS_REGION" \
  --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' \
  --output text)"

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
  echo "No default VPC found. Create one or pass a custom deployment script." >&2
  exit 1
fi

SUBNET_ID="$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
  --query 'Subnets[0].SubnetId' \
  --output text)"

if [ "$SUBNET_ID" = "None" ] || [ -z "$SUBNET_ID" ]; then
  echo "No default subnet found in ${VPC_ID}." >&2
  exit 1
fi

AMI_ID="${AMI_ID:-$(aws ec2 describe-images \
  --region "$AWS_REGION" \
  --owners 099720109477 \
  --filters \
    Name=name,Values='ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*' \
    Name=architecture,Values=x86_64 \
    Name=virtualization-type,Values=hvm \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)}"

echo "VPC: ${VPC_ID}"
echo "Subnet: ${SUBNET_ID}"
echo "AMI: ${AMI_ID}"

if [ ! -f "$KEY_PATH" ]; then
  if aws ec2 describe-key-pairs --region "$AWS_REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
    echo "Key pair ${KEY_NAME} already exists in AWS, but ${KEY_PATH} is missing." >&2
    echo "Either set KEY_NAME to a new name or place the private key at ${KEY_PATH}." >&2
    exit 1
  fi
  aws ec2 create-key-pair \
    --region "$AWS_REGION" \
    --key-name "$KEY_NAME" \
    --key-type rsa \
    --query KeyMaterial \
    --output text > "$KEY_PATH"
  chmod 600 "$KEY_PATH"
  echo "Created SSH key: ${KEY_PATH}"
fi

SG_ID="$(aws ec2 describe-security-groups \
  --region "$AWS_REGION" \
  --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || true)"

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID="$(aws ec2 create-security-group \
    --region "$AWS_REGION" \
    --group-name "$SG_NAME" \
    --description "GenoPredict Docker Compose demo security group" \
    --vpc-id "$VPC_ID" \
    --query GroupId \
    --output text)"
  aws ec2 create-tags --region "$AWS_REGION" --resources "$SG_ID" --tags Key=Project,Value="$APP_NAME"
  echo "Created security group: ${SG_ID}"
fi

add_ingress() {
  local port="$1"
  local cidr="$2"
  aws ec2 authorize-security-group-ingress \
    --region "$AWS_REGION" \
    --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=${port},ToPort=${port},IpRanges=[{CidrIp=${cidr}}]" \
    >/dev/null 2>&1 || true
}

add_ingress 22 "$SSH_CIDR"
add_ingress 3000 "$APP_CIDR"
add_ingress 3001 "$APP_CIDR"
add_ingress 5000 "$APP_CIDR"
add_ingress 9090 "$APP_CIDR"

EXISTING_INSTANCE_ID="$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --filters \
    "Name=tag:Name,Values=${INSTANCE_NAME}" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null || true)"

if [ "$EXISTING_INSTANCE_ID" != "None" ] && [ -n "$EXISTING_INSTANCE_ID" ]; then
  INSTANCE_ID="$EXISTING_INSTANCE_ID"
  STATE="$(aws ec2 describe-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)"
  if [ "$STATE" = "stopped" ]; then
    aws ec2 start-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" >/dev/null
  fi
  echo "Using existing instance: ${INSTANCE_ID}"
else
  INSTANCE_ID="$(aws ec2 run-instances \
    --region "$AWS_REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --subnet-id "$SUBNET_ID" \
    --associate-public-ip-address \
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${VOLUME_SIZE_GB},VolumeType=gp3,DeleteOnTermination=true}" \
    --user-data "file://deploy/aws/user-data.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}},{Key=Project,Value=${APP_NAME}}]" \
    --query 'Instances[0].InstanceId' \
    --output text)"
  echo "Created instance: ${INSTANCE_ID}"
fi

aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-status-ok --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

PUBLIC_DNS="$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicDnsName' \
  --output text)"
PUBLIC_IP="$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)"

echo "Instance public DNS: ${PUBLIC_DNS}"
echo "Instance public IP: ${PUBLIC_IP}"

echo "Creating deployment bundle..."
tar \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./__pycache__' \
  --exclude='./.pytest_cache' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./.dvc/cache' \
  --exclude='./data/raw' \
  --exclude='./data/dbNSFP_extracted' \
  --exclude='./deploy/aws/generated' \
  -czf "$ARCHIVE_PATH" .

echo "Uploading bundle..."
scp -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "$ARCHIVE_PATH" "ubuntu@${PUBLIC_DNS}:/tmp/${APP_NAME}.tar.gz"

GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 12 2>/dev/null || date +%s%N)}"

ssh -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "ubuntu@${PUBLIC_DNS}" bash <<REMOTE
set -euo pipefail
if ! command -v docker >/dev/null || ! sudo docker compose version >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends ca-certificates curl docker.io unzip
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  sudo systemctl enable --now docker
  sudo usermod -aG docker ubuntu || true
fi
if [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo mkdir -p /opt/genopredict
sudo chown -R ubuntu:ubuntu /opt/genopredict
tar -xzf /tmp/${APP_NAME}.tar.gz -C /opt/genopredict
cd /opt/genopredict
cat > .env <<ENV
GENOPREDICT_UID=1000
GENOPREDICT_GID=1000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
DRIFT_CHECK_INTERVAL_SECONDS=300
ENV
mkdir -p data/monitoring reports/monitoring
sudo docker compose up -d --build
sudo docker compose ps
REMOTE

cat > "${GENERATED_DIR}/last-deployment.env" <<EOF
AWS_REGION=${AWS_REGION}
INSTANCE_ID=${INSTANCE_ID}
PUBLIC_DNS=${PUBLIC_DNS}
PUBLIC_IP=${PUBLIC_IP}
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
KEY_PATH=${KEY_PATH}
EOF

echo
echo "Deployment complete."
echo "Frontend:   http://${PUBLIC_DNS}:3000"
echo "Grafana:    http://${PUBLIC_DNS}:3001  admin / ${GRAFANA_PASSWORD}"
echo "MLflow:     http://${PUBLIC_DNS}:5000"
echo "Prometheus: http://${PUBLIC_DNS}:9090"
echo
echo "Saved deployment details to ${GENERATED_DIR}/last-deployment.env"
