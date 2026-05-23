#!/usr/bin/env bash
set -euo pipefail

BUDGET_NAME="${BUDGET_NAME:-genopredict-aws-budget}"
BUDGET_LIMIT_USD="${BUDGET_LIMIT_USD:-65}"
BUDGET_EMAIL="${BUDGET_EMAIL:-}"
AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [ -z "$BUDGET_EMAIL" ]; then
  echo "Set BUDGET_EMAIL first, for example:" >&2
  echo "BUDGET_EMAIL=you@example.com bash deploy/aws/create_budget_alert.sh" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat >"${TMP_DIR}/budget.json" <<EOF
{
  "BudgetName": "${BUDGET_NAME}",
  "BudgetLimit": {
    "Amount": "${BUDGET_LIMIT_USD}",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
EOF

cat >"${TMP_DIR}/notifications-with-subscribers.json" <<EOF
[
  {
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80,
      "ThresholdType": "PERCENTAGE"
    },
    "Subscribers": [
      {
        "SubscriptionType": "EMAIL",
        "Address": "${BUDGET_EMAIL}"
      }
    ]
  }
]
EOF

aws budgets create-budget \
  --account-id "$ACCOUNT_ID" \
  --budget "file://${TMP_DIR}/budget.json" \
  --notifications-with-subscribers "file://${TMP_DIR}/notifications-with-subscribers.json"

echo "Budget alert created for ${BUDGET_LIMIT_USD} USD/month. Confirm the email subscription if AWS asks."
