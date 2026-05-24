# Machine Learning Validation

GenoPredict is strongest as an MLOps and DevSecOps demonstration around a
realistic genomic variant prioritization model. The current model is useful for
decision-support style ranking and workflow automation, but it is not clinically
validated diagnostic software.

## Current Strengths

- XGBoost classifier for tabular genomic annotation features.
- Shared feature contract across training, batch scoring, and online inference.
- Domain-informed features including SIFT, PolyPhen, CADD, allele frequency,
  indel/frame-shift indicators, rarity flags, mutation type, and position
  context.
- MLflow experiment tracking, model registry, and Production alias promotion.
- Promotion is gated by PR-AUC instead of promoting the latest run blindly.
- Evaluation logs probability-quality metrics, including Brier score, log loss,
  and expected calibration error.
- Training exports a calibration table artifact for model review.
- Candidate model benchmarking compares XGBoost with simpler baselines and
  writes reproducible evidence to `docs/MODEL_BENCHMARK.md`.
- SHAP artifacts provide model explainability evidence.
- Runtime prediction logging and drift checks support feedback loops.

## Current Limitations

- The default split is random stratified train/validation/test, which can
  overestimate performance for genomic data if related variants or annotation
  patterns appear across splits.
- No independent external validation dataset is currently required before
  promotion.
- Several inputs are established pathogenicity annotations, so the model should
  be described as an evidence aggregator and prioritizer, not as a replacement
  for expert variant interpretation.
- Probability outputs need calibration review before being treated as risk
  estimates.
- VCF batch scoring depends on feature-store coverage.

## Recommended Next Validation Gates

1. Add chromosome-aware or gene-aware holdout splits.
2. Add temporal validation against a newer ClinVar/dbNSFP release.
3. Add an external holdout dataset that is never used for training or threshold
   selection.
4. Expand the current Logistic Regression and Random Forest baseline benchmark
   with repeated seeds and external validation.
5. Track precision at fixed recall, recall at fixed precision, and confusion
   matrices by variant type and rarity group.
6. Add an abstain path for low-confidence predictions or incomplete features.
7. Require a signed model card update before production promotion.
