from typing import Optional


try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
except Exception:  # pragma: no cover - fallback only used when dependency is absent.
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Gauge = Histogram = None
    generate_latest = None


if Counter is not None:
    PREDICTIONS_TOTAL = Counter(
        "genopredict_predictions_total",
        "Total prediction requests handled by the model service.",
        ["endpoint", "status", "source"],
    )
    PREDICTION_ERRORS_TOTAL = Counter(
        "genopredict_prediction_errors_total",
        "Total prediction errors.",
        ["endpoint"],
    )
    PREDICTION_LATENCY = Histogram(
        "genopredict_prediction_latency_seconds",
        "Prediction latency in seconds.",
        ["endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    )
    PREDICTION_LABEL_TOTAL = Counter(
        "genopredict_prediction_label_total",
        "Total predictions by model label.",
        ["label"],
    )
    LOW_CONFIDENCE_TOTAL = Counter(
        "genopredict_low_confidence_predictions_total",
        "Total predictions with confidence below 0.60.",
        ["endpoint"],
    )
    FEATURE_STORE_LOOKUP_TOTAL = Counter(
        "genopredict_feature_store_lookup_total",
        "Feature store lookup outcomes.",
        ["status"],
    )
    VCF_BATCH_RECORDS_TOTAL = Counter(
        "genopredict_vcf_batch_records_total",
        "Total VCF batch records processed.",
        ["status"],
    )
    MODEL_LOADED = Gauge(
        "genopredict_model_loaded",
        "Whether the production model is loaded: 1 loaded, 0 not loaded.",
    )
else:
    PREDICTIONS_TOTAL = None
    PREDICTION_ERRORS_TOTAL = None
    PREDICTION_LATENCY = None
    PREDICTION_LABEL_TOTAL = None
    LOW_CONFIDENCE_TOTAL = None
    FEATURE_STORE_LOOKUP_TOTAL = None
    VCF_BATCH_RECORDS_TOTAL = None
    MODEL_LOADED = None


def set_model_loaded(is_loaded: bool) -> None:
    if MODEL_LOADED is not None:
        MODEL_LOADED.set(1 if is_loaded else 0)


def observe_prediction(
    endpoint: str,
    status: str,
    source: str,
    latency_seconds: float,
    prediction: Optional[int] = None,
    confidence: Optional[float] = None,
) -> None:
    if PREDICTIONS_TOTAL is None:
        return

    PREDICTIONS_TOTAL.labels(endpoint=endpoint, status=status, source=source).inc()
    PREDICTION_LATENCY.labels(endpoint=endpoint).observe(max(0.0, latency_seconds))

    if status == "error":
        PREDICTION_ERRORS_TOTAL.labels(endpoint=endpoint).inc()

    if prediction is not None:
        label = "pathogenic" if int(prediction) == 1 else "benign"
        PREDICTION_LABEL_TOTAL.labels(label=label).inc()

    if confidence is not None and confidence < 0.60:
        LOW_CONFIDENCE_TOTAL.labels(endpoint=endpoint).inc()


def observe_feature_lookup(status: str) -> None:
    if FEATURE_STORE_LOOKUP_TOTAL is not None:
        FEATURE_STORE_LOOKUP_TOTAL.labels(status=status).inc()


def observe_vcf_batch_records(status: str, count: int) -> None:
    if VCF_BATCH_RECORDS_TOTAL is not None and count > 0:
        VCF_BATCH_RECORDS_TOTAL.labels(status=status).inc(count)


def render_metrics() -> tuple[bytes, str]:
    if generate_latest is None:
        return (
            b"# prometheus_client is not installed\n"
            b"# HELP genopredict_predictions_total Total prediction requests handled by the model service.\n"
            b"# TYPE genopredict_predictions_total counter\n",
            CONTENT_TYPE_LATEST,
        )
    return generate_latest(), CONTENT_TYPE_LATEST
