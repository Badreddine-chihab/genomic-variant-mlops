import os
import sys
import numpy as np
import pandas as pd
import logging
from pathlib import Path

# --- PATH RESOLUTION ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Imports AFTER path fix
import xgboost as xgb
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    average_precision_score, 
    roc_auc_score, 
    f1_score, 
    precision_score, 
    recall_score, 
    accuracy_score
)
import mlflow
import mlflow.xgboost
from src.orchestration.config_utils import ConfigManager, setup_mlflow
from src.features.schema_contract import CATEGORICAL_FEATURES, FEATURE_ORDER, enforce_feature_contract

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_best_threshold(y_true, y_probs, n_points=50):
    thresholds = np.linspace(0.05, 0.95, n_points)
    best_f1 = 0
    best_thresh = 0.5

    for t in thresholds:
        y_pred = (y_probs >= t).astype(int)
        f1 = f1_score(y_true, y_pred)

        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t

    return best_thresh, best_f1


def train_model():
    # 1. INIT CONFIG (ALIGN WITH OTHER SCRIPTS)
    cm = ConfigManager()
    cfg = cm.config
    setup_mlflow(cfg)

    tracking_uri = cfg.mlflow.tracking_uri
    experiment_name = cfg.mlflow.experiment_name

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    xgb_cfg = cfg.training.xgboost
    train_cfg = cfg.training.training

    data_path = cm.get_path("paths.data.final_training")

    logger.info("🚀 Starting training (GPU)")
    logger.info(f"📂 Data: {data_path}")

    df = pd.read_parquet(data_path)

    # 2. PREP DATA
    cat_cols = cfg.features.categorical_cols
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    target = cfg.features.target_col
    X = enforce_feature_contract(df.drop(columns=[target]), fill_missing=False)
    y = df[target]

    # SPLITS
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )

    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42
    )

    # 3. CLASS IMBALANCE
    if xgb_cfg.get("scale_pos_weight_auto", True):
        scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum()
        logger.info(f"⚖️ scale_pos_weight: {scale_pos_weight:.2f}")
    else:
        scale_pos_weight = 1.0

    # 4. MODEL
    model = XGBClassifier(
        n_estimators=xgb_cfg.n_estimators,
        max_depth=xgb_cfg.max_depth,
        learning_rate=xgb_cfg.learning_rate,
        subsample=xgb_cfg.subsample,
        colsample_bytree=xgb_cfg.colsample_bytree,
        tree_method=xgb_cfg.tree_method,
        device=xgb_cfg.device,
        enable_categorical=xgb_cfg.enable_categorical,
        scale_pos_weight=scale_pos_weight,
        eval_metric=xgb_cfg.eval_metric,
        early_stopping_rounds=xgb_cfg.early_stopping_rounds,
        random_state=xgb_cfg.random_state,
        gamma=xgb_cfg.get("gamma", 0),
        reg_alpha=xgb_cfg.get("reg_alpha", 0),
        reg_lambda=xgb_cfg.get("reg_lambda", 1)
    )

    # 5. TRAINING
    with mlflow.start_run(run_name="XGB_Genomic_GPU"):
        mlflow.set_tag("stage", "training")
        logger.info("⚙️ Training...")

        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=100 if train_cfg.verbose else False
        )

        # 6. THRESHOLD OPTIMIZATION
        val_probs = model.predict_proba(X_val)[:, 1]
        best_thresh, val_f1 = find_best_threshold(
            y_val,
            val_probs,
            n_points=train_cfg.get("threshold_n_points", 50)
        )

        test_probs = model.predict_proba(X_test)[:, 1]
        y_pred = (test_probs >= best_thresh).astype(int)

        metrics = {
            "pr_auc": average_precision_score(y_test, test_probs),
            "roc_auc": roc_auc_score(y_test, test_probs),
            "f1_score": f1_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "accuracy": accuracy_score(y_test, y_pred),
            "best_threshold": best_thresh
        }

        mlflow.log_params(dict(xgb_cfg))
        mlflow.log_param("feature_schema_version", "v1")
        mlflow.log_param("feature_count", len(FEATURE_ORDER))
        mlflow.log_param("categorical_feature_count", len(CATEGORICAL_FEATURES))
        mlflow.log_metrics(metrics)

        # ✅ CRITICAL FIX: correct URI format
        mlflow.xgboost.log_model(model, artifact_path="model")

        # ✅ OPTIONAL: register here OR in manager (better separation)
        # 👉 Recommended: REMOVE THIS BLOCK if using manager.py
        """
        try:
            model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
            mv = mlflow.register_model(model_uri, "GenomicVariantModel")
            logger.info(f"Registered model version {mv.version}")
        except Exception as e:
            logger.warning(f"Registration failed: {e}")
        """

        # RESULTS
        logger.info("\n🔥 FINAL RESULTS:")
        for k, v in metrics.items():
            logger.info(f"{k.upper():<15}: {v:.4f}")

        # 7. LOCAL SAVE
        if train_cfg.save_model_locally:
            output_dir = Path(cm.project_root) / train_cfg.model_output_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            model_path = output_dir / "xgboost_gpu_model.json"
            model.save_model(str(model_path))

            logger.info(f"💾 Saved locally: {model_path}")

    logger.info("✅ Training pipeline completed")


if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        sys.exit(1)
