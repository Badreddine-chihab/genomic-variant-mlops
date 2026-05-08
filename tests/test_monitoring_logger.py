import os

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
