import os
import math

import pandas as pd

from src.monitoring.drift_monitor import compute_drift_summary, run_once
from src.monitoring.prediction_logger import load_prediction_events, log_prediction_event, summarize_predictions


def test_prediction_logger_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("GENOPREDICT_MONITORING_LOG", str(tmp_path / "predictions.jsonl"))

    log_prediction_event(
        {
            "endpoint": "/api/predict",
            "source": "api",
            "status": "success",
            "chrom": "11",
            "prediction": 1,
            "probability": 0.91,
            "confidence_score": 0.91,
            "latency_ms": 12.5,
        }
    )

    events = load_prediction_events()
    assert len(events) == 1
    assert events[0]["prediction"] == 1

    summary = summarize_predictions()
    assert summary["total_predictions"] == 1
    assert summary["pathogenic_predictions"] == 1
    assert summary["pathogenic_rate"] == 1.0
    assert summary["by_chromosome"]["11"] == 1

    assert os.path.exists(summary["log_path"])


def test_prediction_logger_sanitizes_non_finite_values(tmp_path, monkeypatch):
    monkeypatch.setenv("GENOPREDICT_MONITORING_LOG", str(tmp_path / "predictions.jsonl"))

    log_prediction_event(
        {
            "endpoint": "/api/predict",
            "source": "api",
            "status": "success",
            "chrom": "11",
            "sift": math.nan,
            "polyphen": float("inf"),
            "prediction": 1,
        }
    )

    event = load_prediction_events()[0]

    assert event["sift"] is None
    assert event["polyphen"] is None


def test_drift_monitor_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("GENOPREDICT_MONITORING_LOG", str(tmp_path / "predictions.jsonl"))

    reference_path = tmp_path / "reference.parquet"
    report_path = tmp_path / "drift.html"
    summary_path = tmp_path / "drift.json"

    pd.DataFrame(
        {
            "CADD": [10.0, 11.0, 12.0],
            "SIFT": [0.1, 0.2, 0.3],
            "PolyPhen": [0.2, 0.3, 0.4],
            "ALT_FREQ": [0.01, 0.02, 0.03],
        }
    ).to_parquet(reference_path)

    log_prediction_event(
        {
            "endpoint": "/api/predict",
            "source": "api",
            "status": "success",
            "cadd": 30.0,
            "sift": 0.9,
            "polyphen": 0.95,
            "alt_freq": 0.4,
            "prediction": 1,
        }
    )

    summary = run_once(reference_path, report_path, summary_path)

    assert summary["status"] == "ok"
    assert summary["current_rows"] == 1
    assert summary["monitored_features"] == 4
    assert summary_path.exists()


def test_drift_monitor_waits_for_prediction_events(tmp_path, monkeypatch):
    monkeypatch.setenv("GENOPREDICT_MONITORING_LOG", str(tmp_path / "empty.jsonl"))

    summary = compute_drift_summary(tmp_path / "not-needed.parquet")

    assert summary["status"] == "waiting_for_predictions"
    assert summary["drift_score"] == 0.0
