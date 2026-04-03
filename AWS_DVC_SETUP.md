# AWS S3 + DVC Setup

## Configuration
- **S3 Bucket**: `aws-s3-bucket-pfa-genomic-classification`
- **DVC Remote**: `s3remote` (default)
- **Remote Path**: `s3://aws-s3-bucket-pfa-genomic-classification/dvc-storage/`
- **AWS Region**: `us-east-1`

## What's Tracked
All data in DVC cache is being synced to S3:
- `data/raw/` — original genomic data
- `data/processed/` — processed variants
- Model artifacts and MLflow runs

## Commands

### Push data to S3
```bash
/home/badr/genomic-variant-mlops/.venv/bin/python -m dvc push
```

### Pull data from S3 (clone/new machine)
```bash
/home/badr/genomic-variant-mlops/.venv/bin/python -m dvc pull
```

### Check what needs syncing
```bash
/home/badr/genomic-variant-mlops/.venv/bin/python -m dvc status -c
```

## AWS Credentials
Stored in `~/.aws/credentials` and `~/.aws/config`

## Status
✅ Initial push in progress...
