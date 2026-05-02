import sys
import logging
import mlflow
from mlflow.tracking import MlflowClient
from pathlib import Path

# --- PATH RESOLUTION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Imports AFTER path fix
from src.orchestration.config_utils import ConfigManager, setup_mlflow

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _resolve_model_uri(client: MlflowClient, experiment_id: str, run_id: str) -> tuple[str, str | None]:
    """
    MLflow 3 stores logged models under mlruns/<experiment>/models/m-... instead
    of the run artifact directory. Prefer that model ID so registry versions point
    at a directory that contains MLmodel.
    """
    if hasattr(client, "search_logged_models"):
        logged_models = client.search_logged_models(
            experiment_ids=[experiment_id],
            filter_string=f"source_run_id = '{run_id}' AND name = 'model'",
            max_results=1,
        )
        if logged_models:
            logged_model = logged_models[0]
            return f"models:/{logged_model.model_id}", logged_model.model_id

    return f"runs:/{run_id}/model", None


def promote_model():
    """
    Promote best model to Production based on PR-AUC threshold
    """

    # 1. INIT CONFIG
    cm = ConfigManager()
    cfg = cm.config
    setup_mlflow(cfg)

    tracking_uri = cfg.mlflow.tracking_uri
    experiment_name = cfg.mlflow.experiment_name

    MODEL_NAME = "GenomicVariantModel"
    THRESHOLD_PR_AUC = 0.80

    logger.info(f"📡 MLflow Tracking URI: {tracking_uri}")
    mlflow.set_tracking_uri(tracking_uri)

    client = MlflowClient()

    # 2. GET EXPERIMENT
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        logger.error(f"❌ Experiment '{experiment_name}' not found.")
        return

    # 3. GET LAST TRAINING RUN (FIXED FILTER 🔥)
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.stage = 'training' AND attributes.status = 'FINISHED'",
        order_by=["attributes.start_time DESC"],
        max_results=1
    )

    if not runs:
        logger.error("❌ No successful TRAINING runs found.")
        logger.info("💡 Make sure train_model logs tag: stage=training")
        return

    last_run = runs[0]
    run_id = last_run.info.run_id
    metrics = last_run.data.metrics

    # 4. CHECK METRICS
    if "pr_auc" not in metrics:
        logger.error("❌ 'pr_auc' metric missing.")
        logger.error(f"Available metrics: {list(metrics.keys())}")
        return

    current_pr_auc = metrics["pr_auc"]

    logger.info(f"📊 Run ID: {run_id}")
    logger.info(f"🎯 PR-AUC: {current_pr_auc:.4f} (threshold={THRESHOLD_PR_AUC})")

    # 5. GOVERNANCE DECISION
    if current_pr_auc < THRESHOLD_PR_AUC:
        logger.warning("🚫 Model NOT promoted (below threshold).")
        return

    logger.info("✅ Model passed threshold → promoting...")

    try:
        model_uri, model_id = _resolve_model_uri(client, experiment.experiment_id, run_id)
        logger.info(f"📦 Model source URI: {model_uri}")

        # Check if model already exists
        try:
            client.get_registered_model(MODEL_NAME)
            logger.info(f"📦 Model '{MODEL_NAME}' exists → creating new version")

            mv = client.create_model_version(
                name=MODEL_NAME,
                source=model_uri,
                run_id=run_id,
                model_id=model_id,
            )

        except mlflow.exceptions.RestException:
            logger.info(f"📦 Creating new registered model '{MODEL_NAME}'")

            mv = mlflow.register_model(model_uri, MODEL_NAME)

        logger.info(f"📦 Registered version: {mv.version}")

        # Set Production alias
        client.set_registered_model_alias(
            name=MODEL_NAME,
            alias="Production",
            version=mv.version
        )

        logger.info(f"🚀 SUCCESS: Model v{mv.version} → @Production")

    except Exception as e:
        logger.error(f"❌ Promotion failed: {e}")
        return


if __name__ == "__main__":
    promote_model()
