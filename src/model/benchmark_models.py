from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.schema_contract import CATEGORICAL_FEATURES, FEATURE_ORDER, enforce_feature_contract
from src.model.metrics import classification_metrics, find_best_threshold
from src.orchestration.config_utils import ConfigManager


def _load_training_frame(sample_size: int | None, random_state: int) -> tuple[pd.DataFrame, pd.Series]:
    cm = ConfigManager()
    cfg = cm.config
    df = pd.read_parquet(cm.get_path("paths.data.final_training"))

    target = cfg.features.target_col
    if sample_size and len(df) > sample_size:
        df, _ = train_test_split(
            df,
            train_size=sample_size,
            stratify=df[target],
            random_state=random_state,
        )

    X = enforce_feature_contract(df.drop(columns=[target]), fill_missing=False)
    y = df[target].astype(int)
    return X, y


def _sklearn_pipeline(model) -> Pipeline:
    numeric_features = [col for col in FEATURE_ORDER if col not in CATEGORICAL_FEATURES]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), numeric_features),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def _xgboost_model(random_state: int) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=450,
        max_depth=6,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.85,
        tree_method="hist",
        device="cpu",
        enable_categorical=True,
        eval_metric="aucpr",
        early_stopping_rounds=30,
        random_state=random_state,
        n_jobs=4,
    )


def _evaluate_model(name: str, model, X_train, X_val, X_test, y_train, y_val, y_test) -> dict[str, float | str]:
    if name == "XGBoost":
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    else:
        model.fit(X_train, y_train)

    val_probs = model.predict_proba(X_val)[:, 1]
    threshold, val_f1 = find_best_threshold(y_val, val_probs)
    test_probs = model.predict_proba(X_test)[:, 1]

    metrics = classification_metrics(y_test, test_probs, threshold=threshold)
    metrics["model"] = name
    metrics["validation_f1_at_threshold"] = float(val_f1)
    return metrics


def run_benchmark(sample_size: int | None, random_state: int) -> pd.DataFrame:
    X, y = _load_training_frame(sample_size=sample_size, random_state=random_state)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=random_state
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=random_state
    )

    scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum()
    models = [
        (
            "Logistic Regression",
            _sklearn_pipeline(
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=random_state,
                )
            ),
        ),
        (
            "Random Forest",
            _sklearn_pipeline(
                RandomForestClassifier(
                    n_estimators=220,
                    max_depth=18,
                    min_samples_leaf=4,
                    class_weight="balanced_subsample",
                    n_jobs=4,
                    random_state=random_state,
                )
            ),
        ),
        ("XGBoost", _xgboost_model(random_state=random_state).set_params(scale_pos_weight=scale_pos_weight)),
    ]

    rows = [
        _evaluate_model(name, model, X_train, X_val, X_test, y_train, y_val, y_test)
        for name, model in models
    ]
    result = pd.DataFrame(rows).sort_values(["pr_auc", "f1_score"], ascending=False).reset_index(drop=True)
    return result


def write_outputs(result: pd.DataFrame, sample_size: int | None, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "model_benchmark_results.csv"
    md_path = output_dir / "MODEL_BENCHMARK.md"

    ordered_cols = [
        "model",
        "pr_auc",
        "roc_auc",
        "f1_score",
        "precision",
        "recall",
        "accuracy",
        "brier_score",
        "log_loss",
        "best_threshold",
    ]
    result[ordered_cols].to_csv(csv_path, index=False)

    display = result[ordered_cols].copy()
    for col in ordered_cols:
        if col != "model":
            display[col] = display[col].map(lambda value: f"{value:.4f}")

    md_path.write_text(
        "\n".join(
            [
                "# Model Benchmark",
                "",
                "This benchmark compares candidate classifiers on the same stratified",
                "train/validation/test split. Thresholds are selected on the validation",
                "split and metrics are reported on the held-out test split.",
                "",
                f"- Sample size: {sample_size or 'full local training dataset'}",
                "- Ranking metric: PR-AUC, then F1 score",
                "- Purpose: model selection evidence for the MLOps project, not clinical validation",
                "",
                display.to_markdown(index=False),
                "",
                "## Interpretation",
                "",
                "The best model should be selected by held-out PR-AUC first because this",
                "pathogenicity task is probability-ranking oriented. F1, precision, recall,",
                "Brier score, and log loss are included to show threshold behavior and",
                "probability quality.",
                "",
                "These results should be expanded with chromosome-aware, gene-aware, temporal,",
                "and external validation before making clinical performance claims.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata = {"sample_size": sample_size, "ranking": ["pr_auc", "f1_score"]}
    (output_dir / "model_benchmark_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark candidate pathogenicity classifiers.")
    parser.add_argument("--sample-size", type=int, default=100000)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()

    sample_size = args.sample_size if args.sample_size > 0 else None
    result = run_benchmark(sample_size=sample_size, random_state=args.random_state)
    write_outputs(result, sample_size=sample_size, output_dir=args.output_dir)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
