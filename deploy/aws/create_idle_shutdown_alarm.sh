#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-genopredict}"
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_NAME="${INSTANCE_NAME:-${APP_NAME}-compose}"
GENERATED_DIR="${GENERATED_DIR:-deploy/aws/generated}"
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-${GENERATED_DIR}/last-deployment.env}"
ALARM_NAME="${ALARM_NAME:-${APP_NAME}-idle-auto-stop}"
CPU_THRESHOLD_PERCENT="${CPU_THRESHOLD_PERCENT:-5}"
IDLE_PERIOD_SECONDS="${IDLE_PERIOD_SECONDS:-300}"
IDLE_EVALUATION_PERIODS="${IDLE_EVALUATION_PERIODS:-6}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
SNS_TOPIC_NAME="${SNS_TOPIC_NAME:-${APP_NAME}-idle-alerts}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -z "${PYTHON_BIN:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi
PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v aws >/dev/null; then
  echo "aws CLI is required." >&2
  exit 1
fi

if [ -f "$DEPLOYMENT_ENV" ]; then
  # shellcheck disable=SC1090
  source "$DEPLOYMENT_ENV"
  AWS_REGION="${AWS_REGION:-us-east-1}"
fi

INSTANCE_ID="${INSTANCE_ID:-$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --filters \
    "Name=tag:Name,Values=${INSTANCE_NAME}" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null || true)}"

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo "No ${INSTANCE_NAME} EC2 instance found. Deploy first or set INSTANCE_ID." >&2
  exit 1
fi

ALARM_ACTIONS=("arn:aws:automate:${AWS_REGION}:ec2:stop")

if [ -n "$ALERT_EMAIL" ]; then
  set +e
  TOPIC_ARN="$(aws sns create-topic \
    --region "$AWS_REGION" \
    --name "$SNS_TOPIC_NAME" \
    --query TopicArn \
    --output text 2>"${TMP_DIR}/sns-error.log")"
  SNS_CREATE_STATUS=$?
  set -e

  if [ "$SNS_CREATE_STATUS" -eq 0 ] && [ -n "$TOPIC_ARN" ] && [ "$TOPIC_ARN" != "None" ]; then
    aws sns subscribe \
      --region "$AWS_REGION" \
      --topic-arn "$TOPIC_ARN" \
      --protocol email \
      --notification-endpoint "$ALERT_EMAIL" \
      >/dev/null

    ALARM_ACTIONS+=("$TOPIC_ARN")
    echo "SNS alert topic created: ${TOPIC_ARN}"
    echo "Confirm the subscription email sent to ${ALERT_EMAIL}."
  else
    echo "Warning: could not create SNS email alert. Continuing with EC2 auto-stop only." >&2
    echo "Reason:" >&2
    sed 's/^/  /' "${TMP_DIR}/sns-error.log" >&2 || true
  fi
fi

set +e
aws cloudwatch put-metric-alarm \
  --region "$AWS_REGION" \
  --alarm-name "$ALARM_NAME" \
  --alarm-description "Stop ${INSTANCE_ID} when GenoPredict EC2 appears idle." \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions "Name=InstanceId,Value=${INSTANCE_ID}" \
  --statistic Average \
  --period "$IDLE_PERIOD_SECONDS" \
  --evaluation-periods "$IDLE_EVALUATION_PERIODS" \
  --datapoints-to-alarm "$IDLE_EVALUATION_PERIODS" \
  --threshold "$CPU_THRESHOLD_PERCENT" \
  --comparison-operator LessThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --unit Percent \
  --alarm-actions "${ALARM_ACTIONS[@]}" \
  2>"${TMP_DIR}/cloudwatch-error.log"
CLOUDWATCH_STATUS=$?
set -e

if [ "$CLOUDWATCH_STATUS" -ne 0 ]; then
  if grep -q "badly formed help string" "${TMP_DIR}/cloudwatch-error.log"; then
    echo "Warning: AWS CLI CloudWatch command failed locally. Trying boto3 fallback." >&2
    if ! "$PYTHON_BIN" -c "import boto3" >/dev/null 2>&1; then
      echo "boto3 is required for the fallback but is not installed in this environment." >&2
      echo "Run: pip install boto3" >&2
      exit 1
    fi

    ALARM_ACTIONS_JSON="$(printf '%s\n' "${ALARM_ACTIONS[@]}" | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"
    export AWS_REGION ALARM_NAME INSTANCE_ID CPU_THRESHOLD_PERCENT IDLE_PERIOD_SECONDS IDLE_EVALUATION_PERIODS ALARM_ACTIONS_JSON
    "$PYTHON_BIN" - <<'PY'
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

cloudwatch = boto3.client("cloudwatch", region_name=os.environ["AWS_REGION"])
try:
    cloudwatch.put_metric_alarm(
        AlarmName=os.environ["ALARM_NAME"],
        AlarmDescription=f"Stop {os.environ['INSTANCE_ID']} when GenoPredict EC2 appears idle.",
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": os.environ["INSTANCE_ID"]}],
        Statistic="Average",
        Period=int(os.environ["IDLE_PERIOD_SECONDS"]),
        EvaluationPeriods=int(os.environ["IDLE_EVALUATION_PERIODS"]),
        DatapointsToAlarm=int(os.environ["IDLE_EVALUATION_PERIODS"]),
        Threshold=float(os.environ["CPU_THRESHOLD_PERCENT"]),
        ComparisonOperator="LessThanOrEqualToThreshold",
        TreatMissingData="notBreaching",
        Unit="Percent",
        AlarmActions=json.loads(os.environ["ALARM_ACTIONS_JSON"]),
    )
except ClientError as exc:
    message = str(exc)
    if "iam:CreateServiceLinkedRole" in message:
        print(
            "CloudWatch needs permission to create the AWS service-linked role "
            "for automatic EC2 stop actions. Ask the AWS account admin to allow "
            "iam:CreateServiceLinkedRole for events.amazonaws.com, then rerun this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(message, file=sys.stderr)
    sys.exit(1)
PY
  else
    cat "${TMP_DIR}/cloudwatch-error.log" >&2
    exit "$CLOUDWATCH_STATUS"
  fi
fi

IDLE_MINUTES=$((IDLE_PERIOD_SECONDS * IDLE_EVALUATION_PERIODS / 60))

echo "Idle shutdown alarm created."
echo "Instance: ${INSTANCE_ID}"
echo "Region: ${AWS_REGION}"
echo "Alarm: ${ALARM_NAME}"
echo "Action: stop EC2 instance after about ${IDLE_MINUTES} minutes below ${CPU_THRESHOLD_PERCENT}% CPU."
