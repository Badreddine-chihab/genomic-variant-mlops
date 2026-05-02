# Genomic Variant MLOps

Production-oriented MLOps project for genomic variant pathogenicity classification using XGBoost, MLflow, and Prefect.

## What This Repo Includes

- End-to-end pipeline orchestration (`run_pipeline.py`)
- Feature engineering and model training (`src/features`, `src/model`)
- MLflow model registry and promotion workflow
- Streamlit UI and FastAPI inference API (`src/ui`, `src/api`)

## Quick Start

1. Install dependencies:
   `pip install -r requirements.txt`
2. Run the pipeline:
   `python run_pipeline.py`
3. Run the UI:
   `python -m streamlit run src/ui/app.py`
4. Run the API:
   `uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`

## Notes

- Main configuration lives in `config/config.yaml`.
- Detailed technical documentation is in `DETAILS.md`.
