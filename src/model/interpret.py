import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import shap
import mlflow
import os
from pathlib import Path
from src.orchestration.config_utils import ConfigManager, setup_mlflow
import xgboost as xgb
import sys 
from src.features.schema_contract import enforce_feature_contract

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Maintenant les imports fonctionneront
from src.orchestration.config_utils import ConfigManager, setup_mlflow


def interpret_model():
    # 1. INITIALISATION
    cm = ConfigManager()
    cfg = cm.config
    setup_mlflow(cfg)
    
    # Chemins
    model_path = Path(cm.project_root) / cfg.training.training.model_output_dir / "xgboost_gpu_model.json"
    data_path = cm.get_path("paths.data.final_training")
    output_dir = Path(cm.project_root) / "reports" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🧐 Interprétation du modèle : {model_path}")

    # 2. CHARGEMENT
    # On charge le modèle XGBoost
    model = xgb.Booster()
    model.load_model(str(model_path))
    
    # On charge un échantillon pour l'explication (SHAP est gourmand en calcul)
    df = pd.read_parquet(data_path)
    X = enforce_feature_contract(df.drop(columns=[cfg.features.target_col]), fill_missing=False)
    
    # Transformation des catégories pour SHAP (il préfère les codes numériques)
    for col in cfg.features.categorical_cols:
        if col in X.columns:
            X[col] = X[col].astype('category').cat.codes

    # 3. CALCUL SHAP
    # On utilise TreeExplainer qui est optimisé pour XGBoost
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X.sample(1000, random_state=42))

    with mlflow.start_run(run_name="Model_Interpretation"):
        mlflow.set_tag("stage", "interpretation")
        # --- Graphique 1 : Summary Plot (Importance globale) ---
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, X.sample(1000, random_state=42), show=False)
        summary_path = output_dir / "shap_summary_plot.png"
        plt.savefig(summary_path, bbox_inches='tight')
        plt.close()
        
        # --- Graphique 2 : Bar Plot (Top Features) ---
        plt.figure(figsize=(10, 6))
        shap.plots.bar(explainer(X.sample(100, random_state=42)), show=False)
        bar_path = output_dir / "shap_bar_plot.png"
        plt.savefig(bar_path, bbox_inches='tight')
        plt.close()

        # Log des graphiques dans MLflow
        mlflow.log_artifact(str(summary_path))
        mlflow.log_artifact(str(bar_path))
        
        print(f"✅ Interprétation terminée. Graphiques sauvegardés dans : {output_dir}")

if __name__ == "__main__":
    interpret_model()
