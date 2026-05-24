# Model Benchmark

This benchmark compares candidate classifiers on the same stratified
train/validation/test split. Thresholds are selected on the validation
split and metrics are reported on the held-out test split.

- Sample size: 100000
- Ranking metric: PR-AUC, then F1 score
- Purpose: model selection evidence for the MLOps project, not clinical validation

| model               |   pr_auc |   roc_auc |   f1_score |   precision |   recall |   accuracy |   brier_score |   log_loss |   best_threshold |
|:--------------------|---------:|----------:|-----------:|------------:|---------:|-----------:|--------------:|-----------:|-----------------:|
| XGBoost             |   0.9593 |    0.9206 |     0.878  |      0.8737 |   0.8822 |     0.8403 |        0.114  |     0.351  |           0.3255 |
| Random Forest       |   0.9534 |    0.9102 |     0.8676 |      0.859  |   0.8764 |     0.8259 |        0.1189 |     0.3633 |           0.3622 |
| Logistic Regression |   0.9341 |    0.8796 |     0.8525 |      0.8097 |   0.9    |     0.7972 |        0.1428 |     0.4397 |           0.3255 |

## Interpretation

The best model should be selected by held-out PR-AUC first because this
pathogenicity task is probability-ranking oriented. F1, precision, recall,
Brier score, and log loss are included to show threshold behavior and
probability quality.

These results should be expanded with chromosome-aware, gene-aware, temporal,
and external validation before making clinical performance claims.
