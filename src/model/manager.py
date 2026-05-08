import logging
import sys
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.register_model import MODEL_ALIAS, MODEL_NAME, MIN_METRIC, promote_best_model
from src.orchestration.config_utils import ConfigManager, setup_mlflow


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def promote_model():
    """
    Promote the best eligible training run to the Production alias.

    Governance rule:
    - only FINISHED runs tagged ``stage=training`` are considered
    - the selected run is the highest PR-AUC run above the configured threshold
    """
    cm = ConfigManager()
    cfg = cm.config
    tracking_uri = setup_mlflow(cfg)
    experiment_name = cfg.mlflow.experiment_name

    logger.info("📡 MLflow Tracking URI: %s", tracking_uri)
    logger.info("🏛️ Promotion rule: best finished training run by pr_auc >= %.4f", MIN_METRIC)
    mlflow.set_tracking_uri(tracking_uri)

    result = promote_best_model(
        client=MlflowClient(),
        model_name=MODEL_NAME,
        alias=MODEL_ALIAS,
        experiment_name=experiment_name,
        min_metric=MIN_METRIC,
        tracking_uri=tracking_uri,
    )

    if result is None:
        logger.warning("🚫 No eligible model was promoted.")
        return None

    logger.info(
        "🚀 SUCCESS: Model v%s → @%s from run %s (%.4f %s)",
        result.version,
        result.alias,
        result.run_id,
        result.metric_value,
        result.metric_name,
    )
    return result


if __name__ == "__main__":
    promote_model()
