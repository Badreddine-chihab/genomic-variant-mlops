#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-genopredict}"
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_NAME="${INSTANCE_NAME:-${APP_NAME}-compose}"
GENERATED_DIR="${GENERATED_DIR:-deploy/aws/generated}"
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-${GENERATED_DIR}/last-deployment.env}"
IDLE_MINUTES="${IDLE_MINUTES:-30}"
CPU_THRESHOLD_PERCENT="${CPU_THRESHOLD_PERCENT:-5}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-300}"
SSH_CONNECT_TIMEOUT_SECONDS="${SSH_CONNECT_TIMEOUT_SECONDS:-15}"

if [ -f "$DEPLOYMENT_ENV" ]; then
  # shellcheck disable=SC1090
  source "$DEPLOYMENT_ENV"
fi

KEY_PATH="${KEY_PATH:-${GENERATED_DIR}/${APP_NAME}-ec2-key.pem}"

if [ -z "${PUBLIC_DNS:-}" ]; then
  PUBLIC_DNS="$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters \
      "Name=tag:Name,Values=${INSTANCE_NAME}" \
      "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].PublicDnsName' \
    --output text 2>/dev/null || true)"
fi

if [ "$PUBLIC_DNS" = "None" ] || [ -z "$PUBLIC_DNS" ]; then
  echo "No running ${INSTANCE_NAME} EC2 host found. Deploy/start it first or set PUBLIC_DNS." >&2
  exit 1
fi

if [ ! -f "$KEY_PATH" ]; then
  echo "SSH key not found at ${KEY_PATH}. Set KEY_PATH or source ${DEPLOYMENT_ENV}." >&2
  exit 1
fi

echo "Installing local idle shutdown on ${PUBLIC_DNS}..."
ssh \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout="$SSH_CONNECT_TIMEOUT_SECONDS" \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=2 \
  -i "$KEY_PATH" \
  "ubuntu@${PUBLIC_DNS}" \
  "IDLE_MINUTES='${IDLE_MINUTES}' CPU_THRESHOLD_PERCENT='${CPU_THRESHOLD_PERCENT}' CHECK_INTERVAL_SECONDS='${CHECK_INTERVAL_SECONDS}' sudo -E bash -s" <<'REMOTE'
set -euo pipefail

cat >/usr/local/sbin/genopredict-idle-shutdown <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/var/lib/genopredict-idle-shutdown/idle-seconds"
IDLE_MINUTES="${IDLE_MINUTES:-30}"
CPU_THRESHOLD_PERCENT="${CPU_THRESHOLD_PERCENT:-5}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-300}"
IDLE_LIMIT_SECONDS=$((IDLE_MINUTES * 60))

mkdir -p "$(dirname "$STATE_FILE")"

read -r _ user nice system idle iowait irq softirq steal _ </proc/stat
total_a=$((user + nice + system + idle + iowait + irq + softirq + steal))
idle_a=$((idle + iowait))
sleep 2
read -r _ user nice system idle iowait irq softirq steal _ </proc/stat
total_b=$((user + nice + system + idle + iowait + irq + softirq + steal))
idle_b=$((idle + iowait))

total_delta=$((total_b - total_a))
idle_delta=$((idle_b - idle_a))
cpu_usage=0
if [ "$total_delta" -gt 0 ]; then
  cpu_usage=$((100 * (total_delta - idle_delta) / total_delta))
fi

idle_seconds=0
if [ -f "$STATE_FILE" ]; then
  idle_seconds="$(cat "$STATE_FILE")"
fi

if [ "$cpu_usage" -le "$CPU_THRESHOLD_PERCENT" ]; then
  idle_seconds=$((idle_seconds + CHECK_INTERVAL_SECONDS))
else
  idle_seconds=0
fi

echo "$idle_seconds" >"$STATE_FILE"
logger "GenoPredict idle shutdown check: cpu=${cpu_usage}% idle_seconds=${idle_seconds}/${IDLE_LIMIT_SECONDS}"

if [ "$idle_seconds" -ge "$IDLE_LIMIT_SECONDS" ]; then
  logger "GenoPredict idle shutdown: stopping host after ${IDLE_MINUTES} idle minutes"
  shutdown -h now "GenoPredict idle shutdown after ${IDLE_MINUTES} minutes below ${CPU_THRESHOLD_PERCENT}% CPU"
fi
SCRIPT

chmod +x /usr/local/sbin/genopredict-idle-shutdown

cat >/etc/systemd/system/genopredict-idle-shutdown.service <<'SERVICE'
[Unit]
Description=GenoPredict local idle shutdown check

[Service]
Type=oneshot
EnvironmentFile=-/etc/default/genopredict-idle-shutdown
ExecStart=/usr/local/sbin/genopredict-idle-shutdown
SERVICE

cat >/etc/systemd/system/genopredict-idle-shutdown.timer <<'TIMER'
[Unit]
Description=Run GenoPredict local idle shutdown checks

[Timer]
OnBootSec=10min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
TIMER

cat >/etc/default/genopredict-idle-shutdown <<ENV
IDLE_MINUTES=${IDLE_MINUTES}
CPU_THRESHOLD_PERCENT=${CPU_THRESHOLD_PERCENT}
CHECK_INTERVAL_SECONDS=${CHECK_INTERVAL_SECONDS}
ENV

systemctl daemon-reload
systemctl enable --now genopredict-idle-shutdown.timer
systemctl list-timers genopredict-idle-shutdown.timer --no-pager
REMOTE

echo "Local idle shutdown installed."
echo "Action: shutdown host after about ${IDLE_MINUTES} minutes below ${CPU_THRESHOLD_PERCENT}% CPU."
