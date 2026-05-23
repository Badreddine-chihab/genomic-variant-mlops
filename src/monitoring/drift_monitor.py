import argparse
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from src.monitoring.evidently_report import FEATURE_COLUMNS, generate_report
from src.monitoring.prediction_logger import events_to_dataframe

try:
    from prometheus_client import Gauge, start_http_server
except Exception:  # pragma: no cover - optional runtime dependency fallback.
    Gauge = None
    start_http_server = None


REFERENCE_DEFAULT = Path("data/processed/final_training_dataset.parquet")
REPORT_DEFAULT = Path("reports/monitoring/latest_drift_report.html")
SUMMARY_DEFAULT = Path("reports/monitoring/latest_drift_summary.json")
LOGGER = logging.getLogger(__name__)


if Gauge is not None:
    DRIFT_SCORE = Gauge(
        "genopredict_data_drift_score",
        "Share of monitored numeric features currently flagged as drifted.",
    )
    DRIFT_FEATURE_FLAG = Gauge(
        "genopredict_data_drift_feature_flag",
        "Whether a monitored feature is currently drifted: 1 drifted, 0 stable.",
        ["feature"],
    )
    DRIFT_CURRENT_ROWS = Gauge(
        "genopredict_data_drift_current_rows",
        "Number of current prediction rows used for the latest drift check.",
    )
    DRIFT_REFERENCE_ROWS = Gauge(
        "genopredict_data_drift_reference_rows",
        "Number of reference rows used for the latest drift check.",
    )
    DRIFT_LAST_SUCCESS = Gauge(
        "genopredict_data_drift_last_success_timestamp_seconds",
        "Unix timestamp of the last successful drift check.",
    )
    DRIFT_LAST_ERROR = Gauge(
        "genopredict_data_drift_last_error_timestamp_seconds",
        "Unix timestamp of the last failed drift check.",
    )
else:
    DRIFT_SCORE = None
    DRIFT_FEATURE_FLAG = None
    DRIFT_CURRENT_ROWS = None
    DRIFT_REFERENCE_ROWS = None
    DRIFT_LAST_SUCCESS = None
    DRIFT_LAST_ERROR = None


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").dropna()


def _normalize_current(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(
        columns={
            "cadd": "CADD",
            "sift": "SIFT",
            "polyphen": "PolyPhen",
            "alt_freq": "ALT_FREQ",
        }
    )


def _feature_summary(reference: pd.DataFrame, current: pd.DataFrame, feature: str) -> Optional[Dict[str, Any]]:
    ref = _numeric_series(reference, feature)
    cur = _numeric_series(current, feature)
    if ref.empty or cur.empty:
        return None

    ref_mean = float(ref.mean())
    cur_mean = float(cur.mean())
    ref_std = float(ref.std(ddof=0))
    mean_delta = abs(cur_mean - ref_mean)

    # A compact heuristic for runtime monitoring: flag when the current mean moves
    # by more than one reference standard deviation, with a small floor for
    # naturally narrow 0..1 genomic scores.
    threshold = max(ref_std, 0.05)
    drifted = mean_delta > threshold

    return {
        "feature": feature,
        "reference_mean": ref_mean,
        "current_mean": cur_mean,
        "reference_std": ref_std,
        "mean_delta": mean_delta,
        "threshold": threshold,
        "drifted": drifted,
        "reference_missing_rate": float(reference[feature].isna().mean()) if feature in reference else None,
        "current_missing_rate": float(current[feature].isna().mean()) if feature in current else None,
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def compute_drift_summary(reference_path: Path) -> Dict[str, Any]:
    current = _normalize_current(events_to_dataframe())
    if current.empty:
        return {
            "status": "waiting_for_predictions",
            "message": "No prediction monitoring events found yet.",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "reference_path": str(reference_path),
            "current_rows": 0,
            "reference_rows": 0,
            "drift_score": 0.0,
            "features": [],
        }

    reference = pd.read_parquet(reference_path)
    features = [
        summary
        for summary in (_feature_summary(reference, current, feature) for feature in FEATURE_COLUMNS)
        if summary is not None
    ]
    drifted = sum(1 for item in features if item["drifted"])
    drift_score = drifted / len(features) if features else 0.0

    return {
        "status": "ok",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reference_path": str(reference_path),
        "current_rows": int(len(current)),
        "reference_rows": int(len(reference)),
        "drifted_features": int(drifted),
        "monitored_features": int(len(features)),
        "drift_score": float(drift_score),
        "features": features,
    }


def write_summary(summary: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(_json_ready(summary), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def update_prometheus(summary: Dict[str, Any]) -> None:
    if DRIFT_SCORE is None:
        return

    DRIFT_SCORE.set(float(summary.get("drift_score", 0.0) or 0.0))
    DRIFT_CURRENT_ROWS.set(int(summary.get("current_rows", 0) or 0))
    DRIFT_REFERENCE_ROWS.set(int(summary.get("reference_rows", 0) or 0))
    if summary.get("status") == "ok":
        DRIFT_LAST_SUCCESS.set(time.time())
    else:
        DRIFT_LAST_ERROR.set(time.time())

    seen_features: Iterable[Dict[str, Any]] = summary.get("features", [])
    for item in seen_features:
        DRIFT_FEATURE_FLAG.labels(feature=str(item["feature"])).set(1 if item.get("drifted") else 0)


def run_once(reference_path: Path, report_path: Path, summary_path: Path) -> Dict[str, Any]:
    summary = compute_drift_summary(reference_path)
    write_summary(summary, summary_path)
    update_prometheus(summary)

    if summary["status"] == "ok":
        try:
            generate_report(reference_path=reference_path, output_path=report_path)
        except Exception as error:
            LOGGER.warning("Drift HTML report generation failed: %s", error)

    return summary


def run_loop(reference_path: Path, report_path: Path, summary_path: Path, interval_seconds: int) -> None:
    while True:
        try:
            summary = run_once(reference_path, report_path, summary_path)
            LOGGER.info(
                "Drift check status=%s current_rows=%s drift_score=%.3f",
                summary.get("status"),
                summary.get("current_rows", 0),
                float(summary.get("drift_score", 0.0) or 0.0),
            )
        except Exception as error:
            LOGGER.exception("Drift check failed: %s", error)
            if DRIFT_LAST_ERROR is not None:
                DRIFT_LAST_ERROR.set(time.time())
        time.sleep(max(30, int(interval_seconds)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run continuous GenoPredict data drift monitoring.")
    parser.add_argument("--reference", type=Path, default=REFERENCE_DEFAULT)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--summary", type=Path, default=SUMMARY_DEFAULT)
    parser.add_argument("--interval-seconds", type=int, default=300)
    # Container metrics endpoint must bind externally for Docker/Kubernetes scraping.
    parser.add_argument("--metrics-host", default="0.0.0.0")  # nosec B104
    parser.add_argument("--metrics-port", type=int, default=8001)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.once:
        summary = run_once(args.reference, args.report, args.summary)
        print(json.dumps(_json_ready(summary), indent=2, sort_keys=True))
        return

    if start_http_server is None:
        LOGGER.warning("prometheus_client is unavailable; drift metrics endpoint will not be exposed.")
    else:
        start_http_server(args.metrics_port, addr=args.metrics_host)
        LOGGER.info("Drift metrics exposed on %s:%s", args.metrics_host, args.metrics_port)

    run_loop(args.reference, args.report, args.summary, args.interval_seconds)


if __name__ == "__main__":
    main()
