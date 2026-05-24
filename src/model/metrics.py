from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def find_best_threshold(y_true, y_probs, n_points: int = 50) -> tuple[float, float]:
    thresholds = np.linspace(0.05, 0.95, n_points)
    best_f1 = 0.0
    best_thresh = 0.5

    for threshold in thresholds:
        y_pred = (np.asarray(y_probs) >= threshold).astype(int)
        score = f1_score(y_true, y_pred, zero_division=0)

        if score > best_f1:
            best_f1 = float(score)
            best_thresh = float(threshold)

    return best_thresh, best_f1


def classification_metrics(y_true, y_probs, threshold: float) -> dict[str, float]:
    y_prob_array = np.asarray(y_probs, dtype=float)
    y_pred = (y_prob_array >= threshold).astype(int)

    return {
        "pr_auc": float(average_precision_score(y_true, y_prob_array)),
        "roc_auc": float(roc_auc_score(y_true, y_prob_array)),
        "f1_score": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "brier_score": float(brier_score_loss(y_true, y_prob_array)),
        "log_loss": float(log_loss(y_true, np.clip(y_prob_array, 1e-7, 1 - 1e-7))),
        "best_threshold": float(threshold),
    }


def calibration_table(y_true, y_probs, n_bins: int = 10) -> pd.DataFrame:
    data = pd.DataFrame({"target": y_true, "probability": np.asarray(y_probs, dtype=float)})
    data["bin"] = pd.cut(
        data["probability"],
        bins=np.linspace(0.0, 1.0, n_bins + 1),
        include_lowest=True,
        labels=False,
    )

    table = (
        data.groupby("bin", observed=False)
        .agg(
            count=("target", "size"),
            mean_predicted_probability=("probability", "mean"),
            observed_pathogenic_rate=("target", "mean"),
        )
        .reset_index()
    )
    table["absolute_calibration_error"] = (
        table["mean_predicted_probability"] - table["observed_pathogenic_rate"]
    ).abs()
    return table


def expected_calibration_error(calibration: pd.DataFrame) -> float:
    if calibration.empty or calibration["count"].sum() == 0:
        return 0.0

    weights = calibration["count"] / calibration["count"].sum()
    return float((weights * calibration["absolute_calibration_error"]).sum())
