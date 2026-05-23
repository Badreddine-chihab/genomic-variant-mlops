import json
import logging
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


DEFAULT_LOG_PATH = Path("data/monitoring/predictions.jsonl")
_LOCK = threading.Lock()
LOGGER = logging.getLogger(__name__)


def get_log_path() -> Path:
    return Path(os.getenv("GENOPREDICT_MONITORING_LOG", DEFAULT_LOG_PATH))


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _sanitize_event(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _json_safe(value) for key, value in row.items()}


def log_prediction_event(event: Dict[str, Any]) -> None:
    """Append one prediction monitoring event to the local JSONL event store."""
    path = get_log_path()

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **{key: _json_safe(value) for key, value in event.items()},
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError as error:
        LOGGER.warning("Prediction monitoring event could not be written to %s: %s", path, error)


def load_prediction_events(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    path = get_log_path()
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(_sanitize_event(json.loads(line)))
            except json.JSONDecodeError:
                continue

    rows.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
    if limit is not None:
        return rows[: max(0, int(limit))]
    return rows


def summarize_predictions() -> Dict[str, Any]:
    rows = load_prediction_events()
    if not rows:
        return {
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "pathogenic_predictions": 0,
            "benign_predictions": 0,
            "pathogenic_rate": 0.0,
            "average_probability": None,
            "average_confidence": None,
            "average_latency_ms": None,
            "low_confidence_predictions": 0,
            "by_source": {},
            "by_chromosome": {},
            "latest_prediction_at": None,
            "log_path": str(get_log_path()),
        }

    df = pd.DataFrame(rows)
    success = df[df["status"] == "success"] if "status" in df else df.iloc[0:0]
    failed_count = int((df["status"] == "error").sum()) if "status" in df else 0

    prediction_series = pd.to_numeric(success["prediction"], errors="coerce") if "prediction" in success else pd.Series(dtype=float)
    pathogenic_count = int((prediction_series == 1).sum())
    benign_count = int((prediction_series == 0).sum())
    successful_count = int(len(success))

    probability = pd.to_numeric(success["probability"], errors="coerce") if "probability" in success else pd.Series(dtype=float)
    confidence = pd.to_numeric(success["confidence_score"], errors="coerce") if "confidence_score" in success else pd.Series(dtype=float)
    latency = pd.to_numeric(df.get("latency_ms"), errors="coerce") if "latency_ms" in df else pd.Series(dtype=float)

    return {
        "total_predictions": int(len(df)),
        "successful_predictions": successful_count,
        "failed_predictions": failed_count,
        "pathogenic_predictions": pathogenic_count,
        "benign_predictions": benign_count,
        "pathogenic_rate": pathogenic_count / successful_count if successful_count else 0.0,
        "average_probability": float(probability.mean()) if not probability.dropna().empty else None,
        "average_confidence": float(confidence.mean()) if not confidence.dropna().empty else None,
        "average_latency_ms": float(latency.mean()) if not latency.dropna().empty else None,
        "low_confidence_predictions": int((confidence < 0.6).sum()) if not confidence.dropna().empty else 0,
        "by_source": df["source"].fillna("unknown").value_counts().to_dict() if "source" in df else {},
        "by_chromosome": df["chrom"].fillna("unknown").astype(str).value_counts().to_dict() if "chrom" in df else {},
        "latest_prediction_at": rows[0].get("timestamp"),
        "log_path": str(get_log_path()),
    }


def events_to_dataframe() -> pd.DataFrame:
    return pd.DataFrame(load_prediction_events())
