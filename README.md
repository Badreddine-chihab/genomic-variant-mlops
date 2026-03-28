# Genomic Variant MLOps

Comprehensive MLOps pipeline for genomic variant classification (pathogenic vs benign).

## Project Overview

This repository contains an end-to-end reproducible pipeline to ingest ClinVar and dbSNP data, process and engineer features, train an XGBoost model (GPU-enabled), and track experiments with MLflow. Data and model versioning is implemented with DVC and MLflow respectively.

Key goals:
- Produce a model to classify genomic variants as pathogenic vs benign.
- Maintain full reproducibility (DVC + Git).
- Support GPU-accelerated training and MLflow tracking.

## Contents

- `data/` - raw and processed datasets (DVC-tracked)
- `src/` - source code
  - `data/` - ingestion scripts
  - `features/` - feature engineering, encoding, optimization
  - `model/` - training and evaluation scripts
- `notebooks/` - exploratory and analysis notebooks
- `dvc.yaml` - pipeline stages definition
- `mlruns/` - MLflow tracking folder (local)
- `Suivi_projet.md` - project status and roadmap
- `ML_ENGINEER_ANALYSIS_REPORT.md` - detailed audit results

## Pipeline (high-level)

1. Download ClinVar (`src/data/download_clinvar.py`) → `data/raw/clinvar.vcf.gz`
2. Process ClinVar (`src/features/process_clinvar.py`) → `data/processed/clinvar_cleaned.csv`
3. Clean labels (`src/features/clean_labels.py`) → `training_base.csv`, `vus_to_predict.csv`
4. Download dbSNP (`src/data/download_dbsnp.py`) → `data/raw/dbsnp_common.vcf.gz`
5. Process dbSNP (`src/features/process_dbsnp.py`) → `data/processed/dbsnp_frequencies.csv`
6. Merge datasets (`src/features/merge_datasets.py`) → `data/processed/final_training_dataset.parquet`
7. Encode & optimize features (`src/features/encode_features.py`, `src/features/optimization.py`) → `data/processed/optimized_training_dataset.parquet`
8. Train model (`src/model/train_model.py`) → model artifact logged to MLflow

The pipeline stages are defined in `dvc.yaml` and can be reproduced with:

```bash
dvc repro
```

## Quickstart (development)

1. Create and activate Python virtual environment (example):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if present; otherwise install key packages
```

2. Inspect DVC pipeline or run a stage:

```bash
dvc dag
dvc repro process_clinvar
```

3. Run training locally (GPU recommended):

```bash
python src/model/train_model.py
# or: python -m src.model.train_model
```

4. Launch MLflow UI to inspect runs:

```bash
mlflow ui --backend-store-uri file://$PWD/mlruns
# then open http://127.0.0.1:5000
```

## Notebooks

- `notebooks/notebook_003.ipynb` - model validation using an MLflow run
- `notebooks/notebook_finaltraining_analysis.ipynb` - comprehensive data & model analysis
- `notebooks/notebook_optimized_analysis.ipynb` - checks on optimized dataset

## Important files and scripts

- `src/data/Stitching_chr.py` - streams and stitches dbNSFP/parquet chunks into a final parquet
- `src/features/encode_features.py` - feature derivation and encoding (Polars, OOM-safe)
- `src/features/optimization.py` - optimization: de-duplication, imputation, multicollinearity fixes, domain interactions
- `src/model/train_model.py` - training entrypoint; logs metrics and saves model with MLflow
- `src/model/eval.py` - cross-validation evaluation script
- `dvc.yaml` - defines stages and dependencies for reproducible runs

## Known issues & current status

- Missing data: `PolyPhen` (~49%) and `SIFT` (~39%) have many missing values; project contains recommended imputation strategies in `optimization.py`.
- Duplicates: ~1,055 duplicate rows detected; removed in optimization.
- Multicollinearity: several highly correlated feature pairs (`is_transition`/`is_transversion`, `ALT_FREQ`/`freq_log`, etc.); `optimization.py` drops redundant columns.
- Current model performance (v1): ROC-AUC ≈ 0.815 (5-fold CV). Improvements expected after data fixes and feature selection.

## Recommendations / Next steps

1. Apply domain-aware imputation for `SIFT`/`PolyPhen` and re-run training.
2. Remove or consolidate highly correlated features, then retrain.
3. Run hyperparameter tuning (Optuna or GridSearch) logged to MLflow.
4. Add continuous integration checks: data schema, DVC reproducibility tests, and unit tests for feature functions.
5. Prepare Docker image and FastAPI endpoint for model serving.

## Troubleshooting

- If you hit memory issues when processing large VCFs, ensure `zcat`-based streaming is used (scripts already use `subprocess` or Polars lazy scanning).
- For MLflow path issues, confirm `mlruns/` is writable and `mlflow.set_tracking_uri` points to `file://$PWD/mlruns`.
- If GPU is unavailable, set `device='cpu'` in training scripts.

## Contact

Author: Badreddine Chihab

---

If you want, I can also generate a `requirements.txt`, a lightweight Dockerfile for training/serving, and a short CI workflow to run the DVC pipeline and tests.
