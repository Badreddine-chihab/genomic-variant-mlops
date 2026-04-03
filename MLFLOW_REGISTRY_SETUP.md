# CI/CD & Model Registry Setup Guide

This guide sets up automated model retraining, validation, and registry management using GitHub Actions.

## ✅ Setup Instructions

### 1. Configure GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

```
AWS_ACCESS_KEY_ID          = your-aws-access-key
AWS_SECRET_ACCESS_KEY      = your-aws-secret-key
MLFLOW_TRACKING_URI        = file:///home/badr/genomic-variant-mlops/mlruns
```

> For local development, use `file://` URI. For production, use S3 or remote MLflow server.

### 2. Workflows Included

#### `retrain.yml`
- **Trigger**: Pushes to `main` that modify data or code
- **Actions**:
  1. Pull latest data from DVC/S3
  2. Retrain model with new data
  3. Evaluate model performance
  4. Register best model to MLflow registry
  5. Push artifacts back to S3
  6. Commit updates to Git

#### `validate.yml`
- **Trigger**: Runs after `retrain.yml` completes
- **Actions**:
  1. Validate model metrics (F1 > 0.75)
  2. Promote to `Production` stage if validation passes
  3. Notify Slack on failure (optional)

### 3. Manual Registry Operations

#### Register Best Model
```bash
python src/model/register_model.py
```
This script:
- Finds the best run by F1 score
- Registers to MLflow Model Registry
- Tags it as `Staging`
- Logs metrics and lineage

#### Check Registry Status
```bash
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
models = client.search_model_versions(\"name='genomic-variant-classifier'\")
for mv in sorted(models, key=lambda x: x.version):
    print(f\"v{mv.version}: {mv.current_stage}\")
"
```

### 4. Promote to Production (Manual)
```bash
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name='genomic-variant-classifier',
    version=1,  # your version number
    stage='Production'
)
"
```

## 📊 Workflow Diagram

```
Data/Code Push
      ↓
  [retrain.yml] ← Triggered by: DVC files, src/**, requirements.txt
      ├─ Pull data from S3
      ├─ Train model
      ├─ Evaluate
      ├─ Register to registry
      └─ Push metrics to S3
      ↓
  [validate.yml] ← Triggered by: retrain success
      ├─ Validate metrics (F1 > 0.75)
      ├─ Promote to Production if valid
      └─ Notify Slack
```

## 🔒 Security Notes

- ✅ AWS credentials stored as GitHub Secrets
- ✅ MLflow artifacts stored in S3 (encrypted at rest)
- ✅ Model registry access controlled via GitHub Actions
- ⚠️ For production: Use temporary AWS STS tokens instead of long-lived keys

## 🚀 Next Steps

1. Set GitHub Secrets (above)
2. Push changes to trigger workflow:
   ```bash
   git add .github/
   git commit -m "feat: add model registry and CI/CD workflows"
   git push
   ```
3. Monitor: **Actions tab → workflow runs**
4. Check Model Registry:
   ```bash
   mlflow ui
   # Open http://localhost:5000
   ```

---

**Status**: ✅ Ready to use
