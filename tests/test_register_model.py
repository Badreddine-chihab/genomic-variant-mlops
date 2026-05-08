from types import SimpleNamespace

from src.model import register_model


def make_run(run_id, metric, start_time):
    return SimpleNamespace(
        info=SimpleNamespace(run_id=run_id, start_time=start_time),
        data=SimpleNamespace(metrics={"pr_auc": metric}),
    )


class FakeClient:
    def __init__(self, runs):
        self.runs = runs

    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id="1")

    def search_runs(self, **kwargs):
        return sorted(
            self.runs,
            key=lambda run: (run.data.metrics.get("pr_auc", float("-inf")), run.info.start_time),
            reverse=True,
        )


def test_find_best_training_run_selects_highest_pr_auc_not_latest():
    latest_weaker = make_run("latest", 0.86, 300)
    older_best = make_run("best", 0.93, 100)

    selected = register_model.find_best_training_run(
        FakeClient([latest_weaker, older_best]),
        min_metric=0.80,
    )

    assert selected.info.run_id == "best"


def test_find_best_training_run_returns_none_when_below_threshold():
    selected = register_model.find_best_training_run(
        FakeClient([make_run("low", 0.79, 100)]),
        min_metric=0.80,
    )

    assert selected is None


def test_find_model_artifact_dir_for_run_uses_matching_mlmodel_run_id(tmp_path):
    matching = tmp_path / "1" / "models" / "m-good" / "artifacts" / "MLmodel"
    other = tmp_path / "1" / "models" / "m-other" / "artifacts" / "MLmodel"
    matching.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    matching.write_text("run_id: run-best\n")
    other.write_text("run_id: run-other\n")

    assert register_model.find_model_artifact_dir_for_run("run-best", tmp_path) == matching.parent


def test_source_uri_for_http_tracking_uses_mlflow_artifact_proxy(tmp_path, monkeypatch):
    mlruns_root = tmp_path / "mlruns"
    artifact_dir = mlruns_root / "1" / "models" / "m-good" / "artifacts"
    artifact_dir.mkdir(parents=True)
    monkeypatch.setattr(register_model, "MLRUNS_ROOT", mlruns_root)

    assert (
        register_model._source_uri_for_artifact_dir(artifact_dir, "http://mlflow:5000")
        == "mlflow-artifacts:/1/models/m-good/artifacts"
    )
