import pandas as pd

from src.model.metrics import (
    calibration_table,
    classification_metrics,
    expected_calibration_error,
    find_best_threshold,
)


def test_find_best_threshold_selects_high_f1_threshold():
    y_true = [0, 0, 1, 1]
    y_probs = [0.05, 0.2, 0.7, 0.9]

    threshold, score = find_best_threshold(y_true, y_probs, n_points=10)

    assert 0.25 <= threshold < 0.75
    assert score == 1.0


def test_classification_metrics_include_calibration_scores():
    metrics = classification_metrics(
        y_true=[0, 0, 1, 1],
        y_probs=[0.05, 0.2, 0.7, 0.9],
        threshold=0.5,
    )

    assert metrics["pr_auc"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert 0 <= metrics["brier_score"] <= 1
    assert metrics["log_loss"] > 0


def test_calibration_table_and_ece_are_weighted():
    table = calibration_table(
        y_true=[0, 0, 1, 1],
        y_probs=[0.1, 0.2, 0.8, 0.9],
        n_bins=2,
    )

    assert isinstance(table, pd.DataFrame)
    assert table["count"].sum() == 4
    assert expected_calibration_error(table) >= 0
