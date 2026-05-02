# ML Engineer Report

## Project State Summary

The project is now aligned with a production-oriented inference architecture:

- FastAPI backend for model serving
- React + Bootstrap frontend for clinical-facing UX
- MLflow model registry integration
- Shared feature schema contract
- VCF parsing and batch prediction support

## Key Engineering Improvements Completed

1. Central feature schema contract in `src/features/schema_contract.py`
2. Robust single prediction path with probability and confidence
3. Main business logic enforced:
   - lookup first by `chrom,pos,ref,alt`
   - if found, predict directly
   - if not found, require manual `SIFT, PolyPhen, CADD, ALT_FREQ`
4. VCF ingestion endpoint and batch prediction endpoint
5. Frontend multi-page workflow (Overview, Predict, VCF Lab)
6. Docker stack migrated from Streamlit-serving to React + API serving
7. Smoke tests for API health, single prediction, and VCF batch flow
8. Downloadable CSV report for VCF batch runs in the frontend

## Model Serving Notes

- Model loaded from `models:/GenomicVariantModel@Production`
- Probability extraction uses pyfunc path with xgboost fallback
- Confidence score uses:
  `max(probability, 1 - probability)`

## Data/Feature Store Integration Notes

- Feature lookup uses S3-backed parquet queries through bridge layer
- Timeout guard added for lookup in API to prevent long hangs in batch mode
- Batch mode returns status per variant:
  `predicted`, `not_found`, `failed`

## API Surface (Current)

- `GET /api/health`
- `GET /api/model-info`
- `GET /api/fetch-features`
- `POST /api/predict`
- `POST /api/upload-vcf`
- `POST /api/vcf-batch-predict`

## Deployment Topology (Current)

- Frontend container (Nginx serving React build) on port `3000`
- API container (Uvicorn/FastAPI) on port `8000`
- MLflow container on port `5000`

Compose orchestration is now centered on the React app and API.

## Recommended Next Steps

1. Add authenticated access and audit logging for clinical environments
2. Add full browser E2E coverage for VCF upload to prediction report flow
3. Add model threshold calibration monitoring and periodic recalibration jobs
4. Add optional PDF report generation if you want a more formal clinical handout
