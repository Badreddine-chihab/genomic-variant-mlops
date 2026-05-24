# Model Card

## Model Details

- **Name:** `GenomicVariantModel`
- **Registry:** MLflow Model Registry
- **Production reference:** `models:/GenomicVariantModel@Production`
- **Model family:** XGBoost classifier
- **Task:** Binary genomic variant pathogenicity classification
- **Classes:** `Benign`, `Pathogenic`

## Intended Use

GenoPredict is designed as an MLOps demonstration for prioritizing genomic
variants by predicted pathogenicity. It supports single variant scoring, VCF
batch workflows, model explainability artifacts, and runtime monitoring.

The output is decision-support style model evidence. It is not a clinical
diagnosis and must not be used as the sole basis for patient care.

## Inputs

The model consumes the feature contract defined in
`src/features/schema_contract.py` and documented in `docs/FEATURE_SCHEMA.md`.
The API can build these features from manual clinical scores or feature-store
records resolved from local parquet/S3.

Important direct inputs include:

- chromosome, position, REF, ALT
- `SIFT`
- `PolyPhen`
- `CADD`
- `ALT_FREQ`
- engineered rarity, mutation type, position, and chromosome context features

## Training and Promotion

Training is orchestrated by `run_pipeline.py`. The pipeline prepares data,
trains XGBoost, evaluates model quality, generates SHAP artifacts, and promotes
the best eligible finished MLflow run.

Promotion is metric gated. The default policy promotes the best finished run
with `pr_auc >= 0.80`; it does not blindly promote the latest run.

## Evaluation

Tracked evidence includes:

- MLflow training metrics and parameters
- cross-validation outputs
- model benchmark evidence comparing XGBoost, Random Forest, and Logistic
  Regression in `docs/MODEL_BENCHMARK.md`
- probability calibration metrics: Brier score, log loss, expected calibration
  error, and calibration table artifact
- PR-AUC promotion gate
- SHAP bar and summary plots

## Monitoring

Runtime monitoring includes:

- prediction event logs in `data/monitoring/predictions.jsonl`
- Prometheus metrics from FastAPI and drift-monitor services
- Grafana dashboards and alerts
- drift summary/report generation from prediction history

## Limitations

- Feature-store coverage determines how many VCF batch records can be scored.
- Manual fallback inputs are simplified and cannot replace expert annotation.
- The demo dataset and model governance are suitable for MLOps evaluation, not
  regulated clinical deployment.
- Current validation uses random stratified splits; external, temporal, or
  chromosome-aware validation should be added before making clinical claims.
- Drift checks depend on enough recent prediction events to provide meaningful
  comparisons.

## Ethical and Safety Notes

Genomic variant interpretation can affect high-stakes decisions. Predictions
should be reviewed by qualified domain experts and interpreted alongside
validated clinical evidence, population context, literature, and laboratory
quality controls.
