import pandas as pd
import numpy as np
import os
import sys
import logging
from pathlib import Path
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

# Import de ton gestionnaire de configuration
from src.orchestration.config_utils import ConfigManager, setup_mlflow

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_best_threshold(y_true, y_probs, n_points=50):
    """Trouve le meilleur seuil sur le jeu de VALIDATION pour optimiser le F1-Score."""
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
    # 1. INITIALISATION CONFIG & MLFLOW
    cm = ConfigManager()
    cfg = cm.config
    setup_mlflow(cfg)
    
    # Raccourcis vers les blocs de config
    xgb_cfg = cfg.training.xgboost
    train_cfg = cfg.training.training
    
    data_path = cm.get_path("paths.data.final_training")
    logger.info(f"🚀 Démarrage de l'entraînement sur GPU (RTX 4070)")
    logger.info(f"📂 Chargement des données : {data_path}")
    
    df = pd.read_parquet(data_path)
    
    # 2. PRÉPARATION DES DONNÉES
    # Gestion des types catégoriels pour XGBoost
    cat_cols = cfg.features.categorical_cols
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    target = cfg.features.target_col
    X = df.drop(columns=[target])
    y = df[target]

    # Split : Train (70%), Val (15%), Test (15%)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42
    )

    # 3. CALCUL DYNAMIQUE DU POIDS (Imbalance)
    if xgb_cfg.get("scale_pos_weight_auto", True):
        scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum()
        logger.info(f"⚖️ Scale_pos_weight calculé : {scale_pos_weight:.2f}")
    else:
        scale_pos_weight = 1.0

    # 4. CONFIGURATION DU MODÈLE
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
        # Ajout des régularisations
        gamma=xgb_cfg.get("gamma", 0),
        reg_alpha=xgb_cfg.get("reg_alpha", 0),
        reg_lambda=xgb_cfg.get("reg_lambda", 1)
    )

    # 5. TRAINING VIA MLFLOW
    with mlflow.start_run(run_name="XGB_Genomic_GPU"):
        logger.info("⚙️ Entraînement en cours...")
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=100 if train_cfg.verbose else False
        )

        # 6. ÉVALUATION ET OPTIMISATION DU SEUIL (Threshold)
        # On prédit sur Validation pour trouver le seuil
        val_probs = model.predict_proba(X_val)[:, 1]
        best_thresh, val_f1 = find_best_threshold(
            y_val, val_probs, n_points=train_cfg.get("threshold_n_points", 50)
        )
        
        # On applique ce seuil sur le Test (Vraie performance)
        test_probs = model.predict_proba(X_test)[:, 1]
        y_pred = (test_probs >= best_thresh).astype(int)

        # Calcul des métriques finales
        metrics = {
            "pr_auc": average_precision_score(y_test, test_probs),
            "roc_auc": roc_auc_score(y_test, test_probs),
            "f1_score": f1_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "accuracy": accuracy_score(y_test, y_pred),
            "best_threshold": best_thresh
        }

        # Logging MLflow
        mlflow.log_params(xgb_cfg)
        mlflow.log_metrics(metrics)
        mlflow.xgboost.log_model(model, "model")

        logger.info("\n🔥 RÉSULTATS FINAUX (Sur Test Set) :")
        for k, v in metrics.items():
            logger.info(f"{k.upper():<15}: {v:.4f}")

        # 7. SAUVEGARDE LOCALE
        if train_cfg.save_model_locally:
            output_dir = Path(cm.project_root) / train_cfg.model_output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            model_path = output_dir / "xgboost_gpu_model.json"
            model.save_model(str(model_path))
            logger.info(f"💾 Modèle sauvegardé localement : {model_path}")

    logger.info("✅ Pipeline d'entraînement terminé avec succès.")

if __name__ == "__main__":
    try:
        train_model()
    except Exception as e:
        logger.error(f"❌ Erreur critique lors de l'entraînement : {e}")
        sys.exit(1)