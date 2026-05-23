# Genomic Variant MLOps

[![Docker Compose CI/CD](https://github.com/Badreddine-chihab/genomic-variant-mlops/actions/workflows/ci-cd-pipeline.yml/badge.svg)](https://github.com/Badreddine-chihab/genomic-variant-mlops/actions/workflows/ci-cd-pipeline.yml)
[![DevSecOps Security Checks](https://github.com/Badreddine-chihab/genomic-variant-mlops/actions/workflows/security.yml/badge.svg)](https://github.com/Badreddine-chihab/genomic-variant-mlops/actions/workflows/security.yml)

Clinical-oriented genomic variant pathogenicity project with:

- XGBoost model training and evaluation
- MLflow tracking and model registry
- FastAPI inference backend
- React + Bootstrap frontend (multi-page dashboard)
- VCF upload and batch prediction workflow
- Runtime monitoring with Prometheus, Grafana, and prediction event logs
- Evidently-compatible drift report generation
- SHAP explainability artifacts in the frontend

## Current App Stack

- Backend API: `src/api/main.py`
- Frontend: `frontend/` (Vite + React + Bootstrap)
- MLflow: `Dockerfile.mlflow`
- Monitoring: `monitoring/` + `src/monitoring/`

Streamlit is kept in repository for reference only and is no longer the primary UI.

## Architecture

The project documentation includes a refreshed, generated SVG diagram set:

- [End-to-end MLOps workflow](docs/project_workflow.svg)
- [Data pipeline](docs/data_pipeline.svg)
- [Training and governance](docs/training_pipeline.svg)
- [Online inference](docs/inference_workflow.svg)
- [VCF batch workflow](docs/vcf_workflow.svg)
- [Monitoring and drift](docs/monitoring_workflow.svg)
- [CI/CD and security](docs/cicd_security_workflow.svg)
- [Deployment workflow](docs/deployment_workflow.svg)

Regenerate them with:

`python docs/generate_workflow_svgs.py`

## Run Locally

1. Install Python deps:
   `pip install -r requirements.txt`
2. Start API:
   `python run_api.py`
3. Start frontend:
   `cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 3000`
4. Open:
   `http://localhost:3000`

The Vite dev server proxies `/api` and `/metrics` to `http://localhost:8000`,
so the browser uses the same relative API paths as the Docker frontend.

## Docker (Recommended)

Run full stack:

`docker compose up --build`

Services:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- MLflow: `http://localhost:5000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Drift monitor metrics: `http://localhost:8001/metrics`

Copy `.env.example` to `.env` before exposing the stack outside your laptop,
then change `GRAFANA_ADMIN_PASSWORD`. The Compose stack also applies basic
container hardening (`no-new-privileges`, dropped Linux capabilities where
safe, non-root API/drift users, and health checks).

## AWS Deployment

For the low-budget AWS version, deploy one EC2 `t3.small` instance and run this same Docker
Compose stack. Do not use EKS for the budget demo.

Start deployment:

`bash deploy/aws/deploy_ec2_compose.sh`

Stop the EC2 instance automatically when it is idle:

`ALERT_EMAIL=you@example.com bash deploy/aws/create_idle_shutdown_alarm.sh`

Destroy it after the demo:

`bash deploy/aws/destroy_ec2_compose.sh`

See `docs/AWS_DEPLOYMENT.md` for IAM permissions, cost guardrails, budget
alerts, idle shutdown, and troubleshooting.

## Argo CD Deployment

Kubernetes manifests are available under `deploy/k8s/base`, with an Argo CD
application manifest at `deploy/argocd/application.yaml`.

Apply it with:

`kubectl apply -f deploy/argocd/application.yaml`

The `Publish Container Images` workflow pushes the API, frontend, and MLflow
images to GHCR on `main`; update `deploy/k8s/base/kustomization.yaml` if you
want Argo CD to deploy a different registry or tag. See
`docs/ARGOCD_DEPLOYMENT.md` for the PVC and access details.

MLflow state is shared with the project root:

- `./mlflow.db` is mounted as the tracking and registry database.
- `./mlruns` is mounted as the artifact store.
- `./data/processed` is mounted read-only into the API for local feature lookup.

The MLflow service also serves artifacts through its HTTP proxy, and the API
mounts `./mlruns` read-only as a compatibility fallback for existing registry
versions that point at `file:///mlflow/mlruns/...`.

The frontend container serves the React build with Nginx and proxies `/api/*`
to the API container. This avoids browser-side `Failed to fetch` issues in
Docker and remote development environments where port `8000` may not be
forwarded separately.

## Training Pipeline

Run the full data-to-production pipeline with:

`python run_pipeline.py`

The pipeline pulls DVC data when needed, stitches raw chromosome files, encodes
the training feature schema, trains XGBoost, runs cross-validation and SHAP
interpretation, then promotes the best eligible training run by PR-AUC to
`GenomicVariantModel@Production` in MLflow.

Promotion is metric-gated. The default policy selects the best finished
training run with `pr_auc >= 0.80`; it does not blindly promote the latest run.
The promotion logic lives in `src/model/register_model.py` and is called by
`src/model/manager.py` during the pipeline governance step. You can also run it
manually when MLflow is available:

`python -m src.model.register_model`

The API exports live metrics at:

`http://localhost:8000/metrics`

Runtime prediction events are stored in:

`data/monitoring/predictions.jsonl`

Monitoring summary endpoints:

- `GET /api/monitoring/summary`
- `GET /api/monitoring/predictions`

Generate a drift report after running predictions:

`python -m src.monitoring.evidently_report`

The report is written to:

`reports/monitoring/latest_drift_report.html`

Docker Compose also runs a continuous drift monitor. It updates:

- `reports/monitoring/latest_drift_report.html`
- `reports/monitoring/latest_drift_summary.json`
- Prometheus metrics such as `genopredict_data_drift_score`

Drift summary endpoint:

- `GET /api/monitoring/drift`

Run one drift check locally:

`python -m src.monitoring.drift_monitor --once`

## CI/CD

The GitHub Actions workflow is Docker Compose-only:

- installs Python and frontend dependencies
- runs Python tests
- builds the React frontend
- validates `docker-compose.yml`
- builds all Compose images

The separate DevSecOps workflow adds:

- Bandit Python SAST
- `pip-audit` for Python dependencies
- `npm audit` for frontend dependencies
- Trivy filesystem, secret, Compose/Dockerfile, and image scans
- Trivy SARIF upload to GitHub code scanning for Security tab visibility
- Dependabot update PRs for Python, npm, Docker, and GitHub Actions

## Demo Flow

1. Start the stack:
   `docker compose up --build`
2. Open the UI:
   `http://localhost:3000`
3. On Predict, try the default benign feature-store variant:
   `11:209271 C>A`
4. For a manual pathogenic example, use:
   `17:43071077 C>T`, `SIFT=0.01`, `PolyPhen=0.98`, `CADD=35`, `ALT_FREQ=0.00001`
5. On VCF Lab, click **Load Demo Batch**, then **Run Batch Prediction**.
   The demo batch includes feature-store hits such as:
   - `11:298524 A>C`
   - `11:299372 G>A`
   - `11:299372 G>C`
   - `11:299391 G>A`
   - `11:533467 C>G`
6. Open Monitoring in the frontend to see prediction history, drift score, and feature drift details.
7. Open Explainability in the frontend to review SHAP plots and the model input feature list.
8. Open Grafana at `http://localhost:3001` for dashboards and provisioned alerts.

There is no AWS deployment step. For a VPS deployment, copy the repository or pull the branch on the server and run:

`docker compose up --build -d`

## Verification

Lightweight smoke checks are included for the core demo paths:

- API health + single prediction
- VCF upload + batch prediction
- Feature lookup fallback from `data/processed/model_ready_dataset.parquet`

Run the full test suite inside the API container:

`docker compose run --rm --no-deps api python -m pytest -q`

Or run lightweight local smoke checks with:

`python -c "from tests.test_api_smoke import test_health_and_predict_smoke, test_vcf_upload_and_batch_predict_smoke; test_health_and_predict_smoke(); test_vcf_upload_and_batch_predict_smoke()"`

## Core Product Logic

- User enters `chrom`, `pos`, `ref`, `alt`
- App tries feature-store lookup using local processed parquet first, then S3
- If found: prediction runs directly
- If not found: manual specs become required (`SIFT`, `PolyPhen`, `CADD`, `ALT_FREQ`)
- Probabilities and confidence are returned and shown in UI
- VCF batch results can be exported from the VCF Lab page as a CSV report

Default demo variant:

`11:209271 C>A`

That variant is present in `data/processed/model_ready_dataset.parquet` and is
used by the UI as the initial prediction example.

## Detailed Documentation

See `DETAILS.md` for architecture, API contracts, and operational notes.
