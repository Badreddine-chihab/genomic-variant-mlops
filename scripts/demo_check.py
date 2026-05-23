from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_PREDICTION = {
    "chrom": "11",
    "pos": 209271,
    "ref": "C",
    "alt": "A",
}


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = raw
        return error.code, body
    except urllib.error.URLError as error:
        return 0, {"detail": str(error.reason)}


def request_text(base_url: str, path: str) -> tuple[int, str]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.URLError as error:
        return 0, str(error.reason)


def check(condition: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
    return condition


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight GenoPredict service smoke check.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="FastAPI base URL.")
    parser.add_argument("--strict-prediction", action="store_true", help="Fail if prediction cannot run.")
    parser.add_argument("--retries", type=int, default=1, help="Retries for initial health check.")
    args = parser.parse_args()

    ok = True
    health_status = 0
    health_body: Any = {}
    for attempt in range(max(1, args.retries)):
        health_status, health_body = request_json(args.base_url, "GET", "/api/health")
        if health_status == 200:
            break
        time.sleep(2)

    ok &= check(health_status == 200, "API health", f"status={health_status}")
    if isinstance(health_body, dict):
        ok &= check(health_body.get("api_status") == "online", "API reports online")
        print(f"model_status={health_body.get('model_status')} model_uri={health_body.get('model_uri')}")

    model_status, model_body = request_json(args.base_url, "GET", "/api/model-info")
    ok &= check(model_status == 200, "Model info endpoint", f"status={model_status}")
    if isinstance(model_body, dict):
        ok &= check(bool(model_body.get("input_features")), "Model feature list exposed")

    metrics_status, metrics_text = request_text(args.base_url, "/metrics")
    ok &= check(metrics_status == 200 and "genopredict" in metrics_text, "Prometheus metrics exposed")

    summary_status, summary_body = request_json(args.base_url, "GET", "/api/monitoring/summary")
    ok &= check(summary_status == 200, "Monitoring summary endpoint", f"status={summary_status}")
    if isinstance(summary_body, dict):
        print(f"monitoring_total_predictions={summary_body.get('total_predictions', 0)}")

    drift_status, drift_body = request_json(args.base_url, "GET", "/api/monitoring/drift")
    ok &= check(drift_status == 200, "Drift endpoint reachable", f"status={drift_status}")
    if isinstance(drift_body, dict):
        print(f"drift_status={drift_body.get('status', 'available')}")

    predict_status, predict_body = request_json(args.base_url, "POST", "/api/predict", DEFAULT_PREDICTION)
    if predict_status == 200:
        ok &= check(True, "Prediction endpoint", "demo variant scored")
    else:
        message = predict_body.get("detail") if isinstance(predict_body, dict) else predict_body
        ok &= check(not args.strict_prediction, "Prediction endpoint", f"not scored: {message}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
