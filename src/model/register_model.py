#!/usr/bin/env python
"""Promote the best eligible MLflow training run to the Production alias."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient


MODEL_NAME = os.getenv("GENOPREDICT_MODEL_NAME", "GenomicVariantModel")
MODEL_ALIAS = os.getenv("GENOPREDICT_MODEL_ALIAS", "Production")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "genomic_pfa")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
METRIC_NAME = os.getenv("GENOPREDICT_PROMOTION_METRIC", "pr_auc")
MIN_METRIC = float(os.getenv("GENOPREDICT_MIN_PR_AUC", "0.80"))
MLRUNS_ROOT = Path(os.getenv("MLFLOW_ARTIFACT_ROOT", Path.cwd() / "mlruns"))


@dataclass(frozen=True)
class PromotionResult:
    model_name: str
    alias: str
    version: str
    run_id: str
    metric_name: str
    metric_value: float
    model_uri: str


def wait_for_mlflow(tracking_uri: str, attempts: int = 60) -> MlflowClient:
    print(f"Waiting for MLflow server at {tracking_uri}...")
    client = MlflowClient(tracking_uri)
    for attempt in range(1, attempts + 1):
        try:
            client.search_experiments(max_results=1)
            print("MLflow server is ready")
            return client
        except Exception as exc:
            print(f"  Attempt {attempt}/{attempts}: {exc}")
            time.sleep(1)
    raise RuntimeError("MLflow server did not become ready")


def _model_uri(run_id: str) -> str:
    return f"runs:/{run_id}/model"


def _source_uri_for_artifact_dir(artifact_dir: Path, tracking_uri: str) -> str:
    parsed = urlparse(tracking_uri)
    if parsed.scheme in {"http", "https"}:
        relative_path = artifact_dir.relative_to(MLRUNS_ROOT).as_posix()
        return f"mlflow-artifacts:/{relative_path}"
    return artifact_dir.resolve().as_uri()


def _run_id_from_mlmodel(mlmodel_path: Path) -> str | None:
    for line in mlmodel_path.read_text().splitlines():
        if line.startswith("run_id:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def find_model_artifact_dir_for_run(run_id: str, mlruns_root: Path = MLRUNS_ROOT) -> Path | None:
    for mlmodel_path in mlruns_root.glob("*/models/m-*/artifacts/MLmodel"):
        try:
            if _run_id_from_mlmodel(mlmodel_path) == run_id:
                return mlmodel_path.parent
        except OSError:
            continue
    return None


def find_best_training_run(
    client: MlflowClient,
    experiment_name: str = EXPERIMENT_NAME,
    metric_name: str = METRIC_NAME,
    min_metric: float = MIN_METRIC,
):
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        print(f"Experiment {experiment_name!r} not found; nothing to promote")
        return None

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.stage = 'training' AND attributes.status = 'FINISHED'",
        order_by=[f"metrics.{metric_name} DESC", "attributes.start_time DESC"],
        max_results=1000,
    )

    eligible_runs = [
        run for run in runs if run.data.metrics.get(metric_name, float("-inf")) >= min_metric
    ]
    if not eligible_runs:
        print(f"No training runs with {metric_name} >= {min_metric:.4f}; nothing to promote")
        return None

    return eligible_runs[0]


def ensure_registered_model(client: MlflowClient, name: str) -> None:
    try:
        client.get_registered_model(name)
    except MlflowException:
        client.create_registered_model(name)
        print(f"Created registered model {name!r}")


def find_existing_version(client: MlflowClient, name: str, run_id: str, source_uri: str):
    try:
        versions = client.search_model_versions(f"name = '{name}'")
    except MlflowException:
        return None

    matching_versions = [
        version for version in versions if version.run_id == run_id and version.source == source_uri
    ]
    if not matching_versions:
        return None

    return max(matching_versions, key=lambda version: int(version.version))


def register_or_reuse_model_version(
    client: MlflowClient,
    model_name: str,
    run_id: str,
    tracking_uri: str = TRACKING_URI,
):
    ensure_registered_model(client, model_name)

    artifact_dir = find_model_artifact_dir_for_run(run_id)
    source_uri = (
        _source_uri_for_artifact_dir(artifact_dir, tracking_uri)
        if artifact_dir is not None
        else _model_uri(run_id)
    )

    existing_version = find_existing_version(client, model_name, run_id, source_uri)
    if existing_version is not None:
        print(f"Reusing {model_name!r} version {existing_version.version} for run {run_id}")
        return existing_version

    print(f"Registering best run from {source_uri}")
    if artifact_dir is not None:
        return client.create_model_version(name=model_name, source=source_uri, run_id=run_id)
    return mlflow.register_model(source_uri, model_name)


def promote_best_model(
    client: MlflowClient,
    model_name: str = MODEL_NAME,
    alias: str = MODEL_ALIAS,
    experiment_name: str = EXPERIMENT_NAME,
    metric_name: str = METRIC_NAME,
    min_metric: float = MIN_METRIC,
    tracking_uri: str | None = None,
) -> PromotionResult | None:
    best_run = find_best_training_run(client, experiment_name, metric_name, min_metric)
    if best_run is None:
        return None

    run_id = best_run.info.run_id
    metric_value = best_run.data.metrics[metric_name]
    model_version = register_or_reuse_model_version(
        client,
        model_name,
        run_id,
        tracking_uri=tracking_uri or mlflow.get_tracking_uri() or TRACKING_URI,
    )

    client.set_registered_model_alias(
        name=model_name,
        alias=alias,
        version=model_version.version,
    )
    print(
        f"Promoted {model_name!r} version {model_version.version} to @{alias} "
        f"from run {run_id} ({metric_name}={metric_value:.4f})"
    )

    return PromotionResult(
        model_name=model_name,
        alias=alias,
        version=str(model_version.version),
        run_id=run_id,
        metric_name=metric_name,
        metric_value=float(metric_value),
        model_uri=_model_uri(run_id),
    )


def main() -> int:
    try:
        client = wait_for_mlflow(TRACKING_URI)
    except Exception as exc:
        print(f"Could not connect to MLflow: {exc}")
        return 1

    mlflow.set_tracking_uri(TRACKING_URI)

    try:
        result = promote_best_model(client)
    except Exception as exc:
        print(f"Could not promote model: {exc}")
        print("The API can still use an existing Production alias or its local fallback model.")
        return 0

    if result is None:
        print("No eligible best training run was promoted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
