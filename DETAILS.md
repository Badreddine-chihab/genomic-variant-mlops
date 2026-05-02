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

### 2.3 Model and MLOps

- Training: `src/model/train_model.py`
- Evaluation: `src/model/eval.py`
- Interpretation: `src/model/interpret.py`
- Promotion/governance: `src/model/manager.py`
- Tracking/registry: MLflow

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

## 6. VCF Workflow

### 6.1 Parse

`/api/upload-vcf` reads VCF rows, skips headers, and extracts:

- `chrom`
- `pos`
- `ref`
- `alt`

Multi-ALT rows are split into one record per ALT allele.

### 6.2 Batch Predict

`/api/vcf-batch-predict`:

1. For each variant, attempts feature-store lookup
2. Predicts only when lookup succeeds
3. Returns per-record status:
   - `predicted`
   - `not_found`
   - `failed`
4. Returns aggregate counters:
   `processed`, `predicted`, `not_found`, `failed`

## 7. Reliability Hardening Implemented

- Lazy import for feature-store dependency in API endpoint path
- VCF route fallback message when multipart dependency is missing
- Feature-store lookup timeout in API to avoid hanging batch calls
- Docker build cleanup with `.dockerignore`
- Smoke tests for API health, single prediction, VCF upload, and VCF batch flow

## 8. VCF Batch Reporting

The React VCF Lab page includes a downloadable CSV report for batch runs.

The export contains:

- variant coordinates
- prediction status
- class label
- probability percentage
- confidence percentage
- batch summary counters

This is designed for professor-facing demos and quick review of batch results.

## 9. Containerization

### 9.1 API Container

- File: `Dockerfile`
- Exposes port `8000`
- Runs `uvicorn src.api.main:app`

### 9.2 Frontend Container

- File: `frontend/Dockerfile`
- Multi-stage build (Node build + Nginx serve)
- Exposes port `3000`

### 9.3 MLflow Container

- File: `Dockerfile.mlflow`
- Exposes port `5000`

### 9.4 Compose

`docker-compose.yml` now runs:

- `mlflow`
- `api`
- `frontend`

Streamlit is removed from compose orchestration.

## 10. Local Development

### API

`python run_api.py`

### Frontend

`cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 3000`

## 11. Operations Notes

- API tracking URI can be overridden by env var:
  `MLFLOW_TRACKING_URI`
- Batch prediction requires feature-store connectivity and AWS credentials
- VCF upload requires `python-multipart`

## 12. Known Constraints

- VCF batch mode predicts only variants found in the feature store
- Variants not found return `not_found` and require alternate handling
- Clinical decision support must remain human-supervised
