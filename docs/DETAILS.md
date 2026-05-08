# Genomic Variant MLOps - Detailed Guide

## 1. Product Overview

This system predicts genomic variant pathogenicity with a production-oriented MLOps architecture.

Primary user flow:

1. Input `chrom`, `pos`, `ref`, `alt`
2. Query feature store for matching variant
3. If found: predict immediately
4. If not found: require manual feature inputs (`SIFT`, `PolyPhen`, `CADD`, `ALT_FREQ`)
5. Return class + probability + confidence

## 2. Architecture

### 2.1 Backend

- Framework: FastAPI
- Main module: `src/api/main.py`
- Model loading: MLflow model registry alias `GenomicVariantModel@Production`
- Feature schema enforcement: `src/features/schema_contract.py`

### 2.2 Frontend

- Framework: React + Vite
- UI library: Bootstrap
- Main app: `frontend/src/App.jsx`
- API client: `frontend/src/api.js`
- Runtime routing: relative `/api/*` calls
- Docker proxy: `frontend/nginx.conf` forwards `/api/*` and `/metrics` to `api:8000`
- Local dev proxy: `frontend/vite.config.js` forwards `/api` and `/metrics` to `localhost:8000`

### 2.3 Model and MLOps

- Training: `src/model/train_model.py`
- Evaluation: `src/model/eval.py`
- Interpretation: `src/model/interpret.py`
- Promotion/governance: `src/model/manager.py`
- Best-run registration: `src/model/register_model.py`
- Tracking/registry: MLflow

The production model is selected by quality, not recency. The default policy
promotes the best finished training run where `pr_auc >= 0.80` to the
`GenomicVariantModel@Production` alias.

Important environment variables:

- `MLFLOW_TRACKING_URI`: MLflow tracking server, default `http://localhost:5000`
- `GENOPREDICT_MODEL_NAME`: registered model name, default `GenomicVariantModel`
- `GENOPREDICT_MODEL_ALIAS`: registry alias, default `Production`
- `GENOPREDICT_PROMOTION_METRIC`: metric used for ranking, default `pr_auc`
- `GENOPREDICT_MIN_PR_AUC`: minimum PR-AUC for promotion, default `0.80`
- `MLFLOW_ARTIFACT_ROOT`: local artifact root used when resolving model files

## 3. API Endpoints

- `GET /api/health`:
  service and model status
- `GET /api/model-info`:
  model metadata and input feature schema
- `GET /api/fetch-features?chrom=&pos=&ref=&alt=`:
  variant lookup in feature store
- `POST /api/predict`:
  single variant prediction
- `POST /api/upload-vcf`:
  parse and preview VCF records
- `POST /api/vcf-batch-predict`:
  batch prediction for parsed VCF records

## 4. Probability and Confidence

Prediction output includes:

- `prediction`:
  class (0 benign, 1 pathogenic)
- `probability`:
  estimated pathogenic probability (0-1)
- `confidence_score`:
  max(probability, 1 - probability)

## 5. Feature Contract

A shared contract is used across training and inference:

- canonical order
- required names
- defaults
- categorical handling

Source: `src/features/schema_contract.py`

This prevents schema drift and `not in index` runtime failures.

## 6. Feature Lookup

Feature lookup is handled by `GET /api/fetch-features`.

The API receives:

- `chrom`
- `pos`
- `ref`
- `alt`

Lookup order:

1. Local processed feature store:
   `data/processed/model_ready_dataset.parquet`
2. S3 feature store via DuckDB:
   `src/ui/scripts/bridge.py`

Docker mounts `./data/processed` into the API container as
`/app/data/processed:ro`, so the local fallback works even though
`data/processed/` is excluded from the image build context by `.dockerignore`.

The local feature-store path can be overridden with:

`GENOPREDICT_FEATURE_STORE_PATH`

Column compatibility:

- identity columns can be raw (`#chr`, `pos(1-based)`, `ref`, `alt`) or encoded
  (`CHROM`, `POS`, `REF`, `ALT`)
- PolyPhen can be read from `Polyphen2_HVAR_score`, `Polyphen2_HDIV_score`, or
  `PolyPhen`

Default demo variant:

`11:209271 C>A`

## 7. VCF Workflow

### 7.1 Parse

`/api/upload-vcf` reads VCF rows, skips headers, and extracts:

- `chrom`
- `pos`
- `ref`
- `alt`

Multi-ALT rows are split into one record per ALT allele.

### 7.2 Batch Predict

`/api/vcf-batch-predict`:

1. For each variant, attempts feature-store lookup
2. Predicts only when lookup succeeds
3. Returns per-record status:
   - `predicted`
   - `not_found`
   - `failed`
4. Returns aggregate counters:
   `processed`, `predicted`, `not_found`, `failed`

## 8. Reliability Hardening Implemented

- Lazy import for feature-store dependency in API endpoint path
- VCF route fallback message when multipart dependency is missing
- Feature-store lookup timeout in API to avoid hanging batch calls
- Local parquet fallback before S3 lookup for Docker/offline demos
- Same-origin frontend API calls through Nginx/Vite proxy to avoid browser fetch failures
- MLflow healthcheck waits until the Production alias registration step has completed
- API waits for healthy MLflow before startup in Docker Compose
- API loads `models:/GenomicVariantModel@Production` and reports `loaded` when registry loading succeeds
- Docker build cleanup with `.dockerignore`
- Smoke tests for API health, single prediction, VCF upload, and VCF batch flow

## 9. VCF Batch Reporting

The React VCF Lab page includes a downloadable CSV report for batch runs.

The export contains:

- variant coordinates
- prediction status
- class label
- probability percentage
- confidence percentage
- batch summary counters

This is designed for professor-facing demos and quick review of batch results.

## 10. Containerization

### 10.1 API Container

- File: `Dockerfile`
- Exposes port `8000`
- Runs `uvicorn src.api.main:app`
- Mounts `./data/processed` read-only for feature lookup
- Mounts `./mlruns` read-only for legacy MLflow file artifact compatibility
- Mounts monitoring/report folders for runtime outputs

### 10.2 Frontend Container

- File: `frontend/Dockerfile`
- Multi-stage build (Node build + Nginx serve)
- Exposes port `3000`
- Proxies `/api/*` to `api:8000`
- Proxies `/metrics` to `api:8000/metrics`

### 10.3 MLflow Container

- File: `Dockerfile.mlflow`
- Exposes port `5000`
- Mounts `./mlruns` and `./mlflow.db`
- Registers/promotes the best eligible model before reporting healthy

### 10.4 Compose

`docker-compose.yml` now runs:

- `mlflow`
- `api`
- `frontend`
- `prometheus`
- `grafana`

Streamlit is removed from compose orchestration.

## 11. Local Development

### API

`python run_api.py`

### Frontend

`cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 3000`

The frontend dev server uses the same relative API paths as production and
proxies them to `localhost:8000`.

## 12. Pipeline and Model Promotion

Run the complete data-to-production flow:

`python run_pipeline.py`

Pipeline tasks:

1. DVC data pull when processed/raw data is missing
2. raw chromosome stitching
3. feature encoding
4. XGBoost training
5. cross-validation
6. SHAP interpretation
7. governance and MLflow promotion

The governance step calls `src/model/manager.py`, which delegates the registry
promotion to `src/model/register_model.py`.

Manual registration is available when you only need to refresh the MLflow alias:

`python -m src.model.register_model`

Manual registration does not train a new model. It inspects existing finished
training runs and promotes the best eligible one.

## 13. Operations Notes

- API tracking URI can be overridden by env var:
  `MLFLOW_TRACKING_URI`
- Local feature lookup requires `data/processed/model_ready_dataset.parquet`
- S3 fallback requires feature-store connectivity and AWS credentials
- VCF upload requires `python-multipart`
- MLflow UI is available at `http://localhost:5000`
- API model state is visible at `GET /api/model-info`

## 14. Verification

Recommended Docker checks:

`docker compose config`

`docker compose build`

`docker compose run --rm --no-deps api python -m pytest -q`

`npm --prefix frontend run build`

Useful smoke checks:

`curl -sS http://localhost:3000/api/model-info`

`curl -sS "http://localhost:3000/api/fetch-features?chrom=11&pos=209271&ref=C&alt=A"`

`curl -sS -X POST http://localhost:3000/api/predict -H "Content-Type: application/json" --data '{"chrom":"11","pos":"209271","ref":"C","alt":"A","sift":0.781,"polyphen":0.0,"cadd":16.120001,"alt_freq":0.000001}'`

Expected healthy model status:

`"model_status": "loaded"`

The fallback status `loaded_local_fallback` means the API could not load the
MLflow registry alias and used the local JSON model instead.

## 15. Known Constraints

- VCF batch mode predicts only variants found in the feature store
- Variants not found return `not_found` and require alternate handling
- Clinical decision support must remain human-supervised
