import os
import sys
import logging
import pandas as pd
import numpy as np
import mlflow
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import make_scorer, average_precision_score, roc_auc_score

# Import du gestionnaire de configuration centralisé
from src.orchestration.config_utils import ConfigManager, setup_mlflow
from src.features.schema_contract import enforce_feature_contract

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def evaluate_model_cv():
    """Exécute une Cross-Validation robuste et logue les résultats dans MLflow."""
    
    # 1. INITIALISATION CONFIG
    cm = ConfigManager()
    cfg = cm.config
    setup_mlflow(cfg)
    
    # Récupération des paramètres depuis training_config.yaml
    xgb_cfg = cfg.training.xgboost
    eval_cfg = cfg.training.training # Contient cv_splits
    
    data_path = cm.get_path("paths.data.final_training")
    logger.info(f"🧪 Évaluation par Cross-Validation (GPU)")
    logger.info(f"📂 Source : {data_path}")

    # 2. CHARGEMENT DES DONNÉES
    df = pd.read_parquet(data_path)
    
    # Categorical casting
    cat_cols = cfg.features.categorical_cols
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    target = cfg.features.target_col
    X = enforce_feature_contract(df.drop(columns=[target]), fill_missing=False)
    y = df[target]

    # 3. CONFIGURATION DU MODÈLE GPU
    # On recalcule le scale_pos_weight sur l'ensemble pour la CV
    spw = (len(y) - y.sum()) / y.sum()

    model = XGBClassifier(
        n_estimators=xgb_cfg.n_estimators,
        max_depth=xgb_cfg.max_depth,
        learning_rate=xgb_cfg.learning_rate,
        tree_method=xgb_cfg.tree_method,
        device=xgb_cfg.device,
        enable_categorical=xgb_cfg.enable_categorical,
        scale_pos_weight=spw,
        random_state=42
    )

    # 4. EXÉCUTION DE LA CV
    n_splits = eval_cfg.get("cv_splits", 5)
    logger.info(f"🔄 Lancement de la {n_splits}-Fold Cross Validation...")
    
    # On définit plusieurs métriques pour l'évaluation
    scoring = {
        'roc_auc': 'roc_auc',
        'pr_auc': make_scorer(average_precision_score, response_method='predict_proba'),
        'accuracy': 'accuracy'
    }

    with mlflow.start_run(run_name=f"XGB_CV_{n_splits}Fold"):
        mlflow.set_tag("stage", "evaluation")
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        
        # cross_validate est plus complet que cross_val_score
        cv_results = cross_validate(
            model, X, y, 
            cv=cv, 
            scoring=scoring, 
            return_train_score=False,
            n_jobs=1 # Obligatoire à 1 pour l'utilisation du GPU
        )

        # 5. CALCUL ET LOG DES RÉSULTATS
        metrics_to_log = {}
        for metric_name in scoring.keys():
            scores = cv_results[f'test_{metric_name}']
            mean_s = scores.mean()
            std_s = scores.std()
            
            metrics_to_log[f"{metric_name}_mean"] = mean_s
            metrics_to_log[f"{metric_name}_std"] = std_s
            
            logger.info(f"📈 {metric_name.upper()}: {mean_s:.4f} (+/- {std_s:.4f})")
            
            # Log des scores individuels par fold
            for i, s in enumerate(scores):
                mlflow.log_metric(f"{metric_name}_fold_{i+1}", s)

        # Log des moyennes finales
        mlflow.log_metrics(metrics_to_log)
        mlflow.log_params(xgb_cfg)
        mlflow.log_param("cv_splits", n_splits)

    logger.info(f"✅ Évaluation terminée. Résultats disponibles dans MLflow.")

if __name__ == "__main__":
    try:
        evaluate_model_cv()
    except Exception as e:
        logger.error(f"❌ Échec de l'évaluation : {e}")
        sys.exit(1)
