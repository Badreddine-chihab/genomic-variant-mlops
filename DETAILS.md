# Genomic Variant MLOps: Detailed Documentation

## 1. Project Goal

This project builds and serves a genomic variant classifier for pathogenicity prediction. It combines:

- data ingestion and preprocessing,
- feature engineering,
- model training and evaluation,
- model governance and promotion,
- inference serving through API and UI.

The repository is designed as an MLOps workflow rather than a notebook-only experiment.

## 2. High-Level Architecture

### Core Components

- Orchestration:
  `run_pipeline.py` coordinates pipeline tasks in sequence.
- Data + features:
  `src/data`, `src/features`.
- Modeling:
  `src/model` for training, evaluation, interpretation, and governance.
- Serving:
  `src/api/main.py` (FastAPI) and `src/ui/app.py` (Streamlit).
- Experiment tracking:
  MLflow (tracking + registry).
- Configuration:
  `config/` (OmegaConf/YAML based).

### Runtime Modes

- Local development:
  local Python environment with local MLflow SQLite backend.
- Containerized mode:
  Docker and docker-compose workflow for MLflow + app stack.

## 3. Repository Structure

- `run_pipeline.py`:
  pipeline entrypoint.
- `src/data/`:
  data stitching utilities.
- `src/features/`:
  feature generation and optimization helpers.
- `src/model/`:
  training, evaluation, SHAP interpretation, model promotion logic.
- `src/api/`:
  inference API and health endpoints.
- `src/ui/`:
  Streamlit application + S3 bridge scripts.
- `src/orchestration/`:
  configuration and infra utilities.
- `config/`:
  training, validation, paths, AWS, and global config.
- `tests/`:
  focused tests for bridge and UI validation logic.

## 4. Configuration

Main config:
`config/config.yaml`

Important blocks:

- `mlflow`:
  tracking URI and experiment name.
- `features`:
  categorical columns and target column.
- `pipeline`:
  runtime behavior (debug/logging mode).
- `paths`:
  local project paths for data and artifacts.
- `aws`:
  cloud settings used by bridge/data access paths.

## 5. Pipeline Flow

`run_pipeline.py` orchestrates the workflow:

1. Data pull (DVC/S3 sync when needed)
2. Chromosome stitching
3. Feature encoding
4. XGBoost training
5. Cross-validation evaluation
6. SHAP-based interpretation
7. Governance and MLflow promotion

Each stage is executed as a task, with predictable ordering and explicit failure propagation.

## 6. Modeling and MLflow

### Training

- `src/model/train_model.py` logs metrics and model artifacts to MLflow.
- Core metrics include PR-AUC, ROC-AUC, precision, recall, F1, accuracy.
- Model is logged under artifact path `model`.

### Evaluation

- `src/model/eval.py` runs CV-based validation and logs fold/global metrics.

### Governance/Promotion

- `src/model/manager.py` selects the latest successful training run.
- Promotion is gated by threshold (`pr_auc` governance rule).
- Model alias `Production` is assigned on successful promotion.

### MLflow Compatibility Note

The governance code resolves MLflow 3 logged-model URIs (`models:/m-...`) before fallback to `runs:/.../model`, preventing missing `MLmodel` path issues when run artifacts are unavailable.

## 7. Inference Interfaces

## FastAPI (`src/api/main.py`)

- `/` and `/api/health`:
  service and model health.
- `/predict`:
  legacy inference endpoint.
- `/api/predict`:
  structured endpoint for frontend clients.
- `/api/fetch-features`:
  fetches variant records from feature store path.

### Streamlit (`src/ui/app.py`)

- Variant search by chromosome/position/ref/alt.
- S3-backed feature retrieval with manual fallback.
- Inference + prediction display.
- Defensive preprocessing now auto-creates/normalizes expected model features to avoid `not in index` crashes.

## 8. Feature Engineering (Inference-Safe)

The inference preprocessing includes:

- base genomic transformations (`REF_Base`, `ALT_Base`, `mutation_type`),
- indel/frame-shift features,
- rarity and damage score features,
- interaction terms and positional bins,
- transition/transversion flags,
- default handling for missing columns.

This keeps single-variant requests compatible with training-time model expectations.

## 9. Running the Project

### Local

1. `pip install -r requirements.txt`
2. `python run_pipeline.py`
3. `python -m streamlit run src/ui/app.py`
4. `uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`

### Optional Docker Flow

- Build and run service containers as defined in the project Docker files and compose settings.

## 10. Testing

Current tests cover focused components:

- MLflow bridge behavior.
- UI input validation behavior.

Recommended extension:

- end-to-end API inference tests,
- feature schema contract tests between training and serving,
- governance threshold and alias integration tests.

## 11. Operational Notes

- Keep `MLFLOW_TRACKING_URI` consistent across training, governance, API, and UI.
- If model alias updates but UI still loads old state, restart Streamlit to clear cached resource loading.
- Ensure AWS credentials are configured when using S3-backed feature retrieval.

## 12. Known Risks / Future Improvements

- Add stricter schema versioning for model input contracts.
- Add automated dependency checks between logged model environment and runtime environment.
- Add CI checks for model artifact availability and alias integrity.
- Expand observability around inference errors and drift.
