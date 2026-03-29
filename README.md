# Genomic Variant Classification MLOps

Project: a production-style MLOps repository for binary classification of genomic variants (pathogenic vs benign) using XGBoost and a Polars-based OOM-safe preprocessing pipeline.

---

## Repository layout

- `data/` - raw and processed data. Key artifacts:
  - `data/processed/final_training_dataset.parquet` — full assembled dataset (model-ready)
  - `data/processed/optimized_training_dataset.parquet` — optimized dataset used for training
- `src/` - source code
  - `src/data/Stitching_chr.py` — stream-extract and per-chromosome cleaning from dbNSFP gz files (Polars lazy + parquet sinks)
  - `src/features/encode_features.py` — feature engineering and encoding (Polars lazy pipeline)
  - `src/features/optimization.py` — dataset optimization (dedupe, impute, drop correlated derived features)
  - `src/model/train_model.py` — training script (XGBoost GPU-enabled, MLflow logging)
  - `src/model/eval.py` — cross-validation evaluation script with MLflow logging
- `notebooks/` - exploratory and analysis notebooks
- `mlruns/` - MLflow tracking artifacts (local tracking URI used by scripts)

---

## Quick summary

This project ingests dbNSFP variant data (tab-separated gz chunks), extracts a small set of model-relevant columns, performs OOM-safe cleaning with Polars, engineers domain features (rarity, CADD, frameshift flags, etc.), optimizes the dataset (dedupe, imputation, drop correlated derived features), and trains an XGBoost classifier with GPU support (RTX 40-series). Training and evaluation artifacts (metrics, params, model) are logged to MLflow using a local `mlruns` store.

## Dataset notes (from repository analysis)

- The assembled dataset contains on the order of a few hundred thousand rows (report indicates ~354,290 samples).
- Target encoding in preprocessing: `clinvar_clnsig` is mapped to a binary target (`pathogenic` → 1, `benign` → 0) and rows without an explicit label are dropped.
- Important features include: `CADD`, `SIFT`, `PolyPhen`, `ALT_FREQ` (gnomAD_exomes_AF), `Impact_Score`, and engineered indicators for rarity and frameshift.

## Reproducible local dev environment

1. Create and activate a Python virtual environment (example):

   python3 -m venv .venv
   source .venv/bin/activate

2. Install dependencies:

   pip install -r requirements.txt

3. Ensure you have a parquet engine installed (`pyarrow` preferred). See `requirements.txt`.

4. Confirm MLflow local tracking directory is writable: the project uses `file:///home/badr/genomic-variant-mlops/mlruns` by default in training scripts. You can change this in the scripts or set `MLFLOW_TRACKING_URI` environment variable.

## Common tasks

- Build the model-ready dataset from dbNSFP gz files (run inside `src/data`):

  cd src/data
  python Stitching_chr.py

  This will stream each `dbNSFP4.9a_variant.chr*.gz` file, extract selected columns, clean them, and write per-chromosome parquet chunks to `data/processed/`.

- Run encoding & feature engineering (Polars, memory-safe):

  cd src/features
  python -c "from encode_features import encode_genetic_features; encode_genetic_features('path/to/input.parquet','path/to/output.parquet')"

- Optimize dataset (dedupe, impute, drop correlated features):

  cd src/features
  python optimization.py

- Train model (GPU recommended):

  cd src/model
  python train_model.py

  The script expects `/home/badr/genomic-variant-mlops/data/processed/optimized_training_dataset.parquet` by default; edit the script or pass a dataset path directly in `__main__`.

- Evaluate / cross-validate:

  cd src/model
  python eval.py

## MLflow

- Tracking URI used in scripts: a local file store under the project `mlruns/` directory. To view runs: start the MLflow UI and point to the same store:

  mlflow ui --backend-store-uri file:///full/path/to/mlruns

## Engineering & production considerations

- Polars lazy scanning and parquet sinks are used to avoid OOM when processing large dbNSFP files.
- Training uses XGBoost with `tree_method='hist'` and `device='cuda'` where a CUDA-capable GPU is available. If you do not have a GPU, change `device` to `cpu` in `train_model.py` and `eval.py`.
- The optimization step intentionally imputes missing values for `SIFT`, `PolyPhen`, and `CADD` with sentinel values (-1.0) to allow tree-based models to treat missingness as a signal.
- The project includes a small suite of notebooks in `/notebooks` for analysis and diagnostics. They demonstrate model loading from MLflow runs and cross-validation.

## Troubleshooting

- Parquet engine errors: install `pyarrow` (preferred) or `fastparquet`.
- GPU training errors: verify CUDA toolkit and compatible `xgboost` GPU build are installed. If unavailable, set `device='cpu'`.
- Permission errors writing `mlruns/`: run scripts with a user that has write access to the project directory or change the MLflow tracking URI.

## File references

- Main preprocessing: `src/data/Stitching_chr.py`
- Feature engineering: `src/features/encode_features.py`
- Optimization: `src/features/optimization.py`
- Training: `src/model/train_model.py`
- Evaluation: `src/model/eval.py`

---

If you want, I can now:
- run a quick dependency check and pin exact versions using the environment here, or
- run the data pipeline on the available parquet dataset and produce a small manifest with row counts.

Please tell me which next step you prefer.
