#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-genopredict}"
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_NAME="${INSTANCE_NAME:-${APP_NAME}-compose}"
KEY_NAME="${KEY_NAME:-${APP_NAME}-ec2-key}"
SG_NAME="${SG_NAME:-${APP_NAME}-compose-sg}"
GENERATED_DIR="${GENERATED_DIR:-deploy/aws/generated}"
KEY_PATH="${GENERATED_DIR}/${KEY_NAME}.pem"
ALARM_NAME="${ALARM_NAME:-${APP_NAME}-idle-auto-stop}"
SNS_TOPIC_NAME="${SNS_TOPIC_NAME:-${APP_NAME}-idle-alerts}"

INSTANCE_ID="${INSTANCE_ID:-$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --filters \
    "Name=tag:Name,Values=${INSTANCE_NAME}" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null || true)}"

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo "No active ${INSTANCE_NAME} EC2 instance found."
else
  echo "Terminating ${INSTANCE_ID}..."
  aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" >/dev/null
  aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
  echo "Instance terminated."
fi

echo "Deleting idle shutdown alarm ${ALARM_NAME}..."
aws cloudwatch delete-alarms --region "$AWS_REGION" --alarm-names "$ALARM_NAME" >/dev/null 2>&1 || true

TOPIC_ARN="$(aws sns list-topics \
  --region "$AWS_REGION" \
  --query 'Topics[].TopicArn' \
  --output text 2>/dev/null \
  | tr '\t' '\n' \
  | grep -E ":${SNS_TOPIC_NAME}$" \
  | head -n 1 || true)"

if [ "$TOPIC_ARN" != "None" ] && [ -n "$TOPIC_ARN" ]; then
  echo "Deleting SNS topic ${TOPIC_ARN}..."
  aws sns delete-topic --region "$AWS_REGION" --topic-arn "$TOPIC_ARN" || true
fi

SG_ID="$(aws ec2 describe-security-groups \
  --region "$AWS_REGION" \
  --filters "Name=group-name,Values=${SG_NAME}" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || true)"

if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  echo "Deleting security group ${SG_ID}..."
  aws ec2 delete-security-group --region "$AWS_REGION" --group-id "$SG_ID" || true
fi

if aws ec2 describe-key-pairs --region "$AWS_REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
  echo "Deleting AWS key pair ${KEY_NAME}..."
  aws ec2 delete-key-pair --region "$AWS_REGION" --key-name "$KEY_NAME" || true
fi

if [ -f "$KEY_PATH" ]; then
  echo "Removing local private key ${KEY_PATH}..."
  rm -f "$KEY_PATH"
fi

echo "Cleanup complete. Check AWS Billing/EC2 console for any remaining resources."
