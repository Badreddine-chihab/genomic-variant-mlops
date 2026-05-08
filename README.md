# Genomic Variant MLOps

Clinical-oriented genomic variant pathogenicity project with:

- XGBoost model training and evaluation
- MLflow tracking and model registry
- FastAPI inference backend
- React + Bootstrap frontend (multi-page dashboard)
- VCF upload and batch prediction workflow
- Runtime monitoring with Prometheus, Grafana, and prediction event logs
- Evidently-compatible drift report generation

## Current App Stack

- Backend API: `src/api/main.py`
- Frontend: `frontend/` (Vite + React + Bootstrap)
- MLflow: `Dockerfile.mlflow`
- Monitoring: `monitoring/` + `src/monitoring/`

Streamlit is kept in repository for reference only and is no longer the primary UI.

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
- Grafana: `http://localhost:3001` (`admin` / `admin`)

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

## CI/CD

The GitHub Actions workflow is Docker Compose-only:

- installs Python and frontend dependencies
- runs Python tests
- builds the React frontend
- validates `docker-compose.yml`
- builds all Compose images

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
