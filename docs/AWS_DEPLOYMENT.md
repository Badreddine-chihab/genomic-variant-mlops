# AWS Deployment Guide

This project should be deployed on AWS as a single EC2 instance running Docker
Compose. This keeps the cost predictable for a school demo.

Do not use EKS for the budget version. EKS adds a managed Kubernetes control
plane cost before you pay for compute, storage, IP addresses, or networking.

## Target Architecture

- One EC2 instance: default `t3.small`
- Ubuntu 22.04
- Docker Compose
- One public IPv4 address
- One security group
- One 30 GiB gp3 EBS root volume
- No NAT Gateway
- No Load Balancer
- No RDS
- No EKS

Public demo ports:

- `3000`: React frontend
- `3001`: Grafana
- `5000`: MLflow
- `9090`: Prometheus

The API and drift monitor still run in Compose, but public access to `8000` and
`8001` is not opened by the script. The frontend proxies API calls internally.

## Cost Guardrails

For May 16, 2026 to July 1, 2026, the default `t3.small` approach should fit
roughly inside a 70 USD budget if traffic is low and no extra AWS services are
left running.

Main cost drivers:

- EC2 instance hours
- public IPv4 address hours
- EBS volume storage
- small internet transfer charges

Avoid:

- EKS
- NAT Gateway
- Application Load Balancer
- RDS
- Elastic IP addresses that are allocated but not needed
- snapshots you forget to delete

## IAM Permissions Needed

The current AWS user must be allowed to manage a small EC2 deployment. If you
see `UnauthorizedOperation`, ask the AWS account owner/admin to attach a policy
like this to your IAM user for the demo period:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GenoPredictEC2Demo",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "ec2:RunInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:TerminateInstances",
        "ec2:CreateTags",
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:CreateKeyPair",
        "ec2:DeleteKeyPair"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadCallerIdentity",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    },
    {
      "Sid": "OptionalBudgetAlert",
      "Effect": "Allow",
      "Action": [
        "budgets:CreateBudget",
        "budgets:DescribeBudgets",
        "budgets:ModifyBudget"
      ],
      "Resource": "*"
    },
    {
      "Sid": "OptionalIdleShutdownAlarm",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms",
        "cloudwatch:DescribeAlarms",
        "sns:CreateTopic",
        "sns:Subscribe",
        "sns:ListTopics",
        "sns:DeleteTopic"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowCloudWatchServiceLinkedRole",
      "Effect": "Allow",
      "Action": [
        "iam:CreateServiceLinkedRole"
      ],
      "Resource": "arn:aws:iam::*:role/aws-service-role/events.amazonaws.com/AWSServiceRoleForCloudWatchEvents",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "events.amazonaws.com"
        }
      }
    }
  ]
}
```

For a class project, attaching AWS managed `AmazonEC2FullAccess` temporarily is
also common, but the custom policy above is narrower.

## Deploy

From the repository root:

```bash
bash deploy/aws/deploy_ec2_compose.sh
```

Useful options:

```bash
AWS_REGION=us-east-1 INSTANCE_TYPE=t3.small bash deploy/aws/deploy_ec2_compose.sh
```

Restrict public app access to your current IP:

```bash
MY_IP="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
APP_CIDR="${MY_IP}/32" bash deploy/aws/deploy_ec2_compose.sh
```

If your AWS account allows non-free-tier instances and you need more memory:

```bash
INSTANCE_TYPE=t3.medium bash deploy/aws/deploy_ec2_compose.sh
```

The script saves deployment details to:

```text
deploy/aws/generated/last-deployment.env
```

## Create a Budget Alert

If your IAM user has AWS Budgets permission:

```bash
BUDGET_EMAIL=you@example.com BUDGET_LIMIT_USD=65 bash deploy/aws/create_budget_alert.sh
```

If this command fails, create the budget manually in the AWS Console:

- Budget type: Cost budget
- Period: Monthly
- Limit: 65 USD
- Alert at: 80 percent actual cost

## Create an Idle Shutdown Alert

Create a CloudWatch alarm that stops the EC2 instance when it appears unused.
By default, it stops the instance after about 30 minutes with average CPU at or
below 5 percent:

```bash
bash deploy/aws/create_idle_shutdown_alarm.sh
```

To receive an email when the alarm triggers, pass `ALERT_EMAIL` and confirm the
AWS SNS subscription email:

```bash
ALERT_EMAIL=you@example.com bash deploy/aws/create_idle_shutdown_alarm.sh
```

If your IAM user lacks `sns:CreateTopic` or `sns:Subscribe`, run the same script
without `ALERT_EMAIL`. The CloudWatch alarm can still stop the EC2 instance; it
just will not send an email notification.

If your IAM user also cannot create the CloudWatch service-linked role
(`iam:CreateServiceLinkedRole`), install the local shutdown timer on the EC2
host instead:

```bash
bash deploy/aws/install_local_idle_shutdown.sh
```

This uses SSH and systemd on the instance, so it does not require CloudWatch,
SNS, or extra IAM permissions after the EC2 host is deployed.

Useful options:

```bash
CPU_THRESHOLD_PERCENT=3 IDLE_PERIOD_SECONDS=300 IDLE_EVALUATION_PERIODS=12 \
  ALERT_EMAIL=you@example.com bash deploy/aws/create_idle_shutdown_alarm.sh
```

This example waits about 60 minutes because `300 seconds * 12 periods = 60
minutes`. Stopping the instance pauses EC2 compute charges, but the EBS volume
and public IPv4 address can still generate small charges. Use the destroy
script when the demo is finished.

## Operate the Server

SSH:

```bash
source deploy/aws/generated/last-deployment.env
ssh -i "$KEY_PATH" ubuntu@"$PUBLIC_DNS"
```

Inside the server:

```bash
cd /opt/genopredict
docker compose ps
docker compose logs -f
docker compose pull
docker compose up -d --build
```

URLs:

- Frontend: `http://PUBLIC_DNS:3000`
- Grafana: `http://PUBLIC_DNS:3001`
- MLflow: `http://PUBLIC_DNS:5000`
- Prometheus: `http://PUBLIC_DNS:9090`

Grafana credentials are printed by the deploy script and stored in
`deploy/aws/generated/last-deployment.env`.

## Destroy After the Demo

Run this when you are finished, especially after July 1:

```bash
bash deploy/aws/destroy_ec2_compose.sh
```

Then check the AWS Console:

- EC2 instances: terminated
- Elastic IPs: none allocated unless you intentionally created one
- Volumes: no unattached volumes
- Snapshots: none unexpected
- NAT Gateways: none
- Load Balancers: none

## Troubleshooting

### `UnauthorizedOperation`

Your IAM user lacks permissions. Use the IAM policy above.

### `iam:CreateServiceLinkedRole`

The first CloudWatch alarm with an automatic EC2 stop action may need to create
the AWS service-linked role `AWSServiceRoleForCloudWatchEvents`. Add the
`AllowCloudWatchServiceLinkedRole` statement from the IAM policy above, then
rerun the idle shutdown script.

### `badly formed help string`

Some AWS CLI builds fail locally on the CloudWatch alarm command before sending
the request. The idle shutdown script falls back to `boto3` for this case. If
you see a message saying `boto3` is missing, install the project dependency:

```bash
pip install boto3
```

### Docker build is slow

The first build on EC2 downloads Python and npm dependencies. Later builds are
faster because Docker caches layers.

### App is down after reboot

SSH into the instance:

```bash
cd /opt/genopredict
docker compose up -d
docker compose ps
```

### Out of memory

Use `t3.medium` instead of `t3.small` if your AWS account allows it. The script
also creates a 4 GiB swap file to reduce memory failures during image builds.
