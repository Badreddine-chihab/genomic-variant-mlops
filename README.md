# Genomic Variant MLOps

Clinical-oriented genomic variant pathogenicity project with:

- XGBoost model training and evaluation
- MLflow tracking and model registry
- FastAPI inference backend
- React + Bootstrap frontend (multi-page dashboard)
- VCF upload and batch prediction workflow

## Current App Stack

- Backend API: `src/api/main.py`
- Frontend: `frontend/` (Vite + React + Bootstrap)
- MLflow: `Dockerfile.mlflow`

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

## Docker (Recommended)

Run full stack:

`docker compose up --build`

Services:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- MLflow: `http://localhost:5000`

## Verification

Lightweight smoke checks are included for the core demo paths:

- API health + single prediction
- VCF upload + batch prediction

Run them with:

`python -c "from tests.test_api_smoke import test_health_and_predict_smoke, test_vcf_upload_and_batch_predict_smoke; test_health_and_predict_smoke(); test_vcf_upload_and_batch_predict_smoke()"`

## Core Product Logic

- User enters `chrom`, `pos`, `ref`, `alt`
- App tries feature-store lookup
- If found: prediction runs directly
- If not found: manual specs become required (`SIFT`, `PolyPhen`, `CADD`, `ALT_FREQ`)
- Probabilities and confidence are returned and shown in UI
- VCF batch results can be exported from the VCF Lab page as a CSV report

## Detailed Documentation

See `DETAILS.md` for architecture, API contracts, and operational notes.
