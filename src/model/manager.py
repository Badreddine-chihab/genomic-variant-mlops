import os
import sys
import logging
from pathlib import Path

# --- BLOC DE RÉSOLUTION DE CHEMIN (DOIT ÊTRE EN HAUT) ---
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# -------------------------------------------------------

import mlflow
from mlflow.tracking import MlflowClient
from src.orchestration.config_utils import ConfigManager

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def manage_model():
    # 1. INITIALISATION CONFIG & CHEMINS
    cm = ConfigManager(project_root=PROJECT_ROOT)
    cfg = cm.config
    
    # ---------------------------------------------------------
    # 🔧 FIX MLFLOW : Forcer la lecture depuis la base SQLite
    # ---------------------------------------------------------
    tracking_uri = cfg.mlflow.tracking_uri
    experiment_name = cfg.mlflow.experiment_name
    
    logger.info(f"📡 Connexion au Model Registry via : {tracking_uri}")
    
    # On force l'environnement global et on instancie un client spécifique
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    # ---------------------------------------------------------

    # 2. RECHERCHE DE L'EXPÉRIENCE
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        logger.error(f"❌ Expérience '{experiment_name}' non trouvée dans la base de données !")
        # Affiche ce qui existe réellement dans la DB pour aider au debug
        exps = [e.name for e in client.search_experiments()]
        logger.info(f"🔍 Expériences détectées dans ce dossier : {exps}")
        return

    # 3. IDENTIFICATION DU MEILLEUR RUN
    logger.info("🏆 Recherche du meilleur modèle basé sur le F1-Score...")
    
    # On cherche tous les runs de cette expérience, triés par F1-Score décroissant
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.f1_score DESC"],
        max_results=1
    )

    if not runs:
        logger.warning("⚠️ Aucun run terminé trouvé pour cette expérience.")
        return

    best_run = runs[0]
    best_f1 = best_run.data.metrics.get('f1_score', 0)
    run_id = best_run.info.run_id

    logger.info(f"✅ Meilleur run identifié : {run_id} (F1-Score = {best_f1:.4f})")

    # 4. ENREGISTREMENT ET PROMOTION
    model_name = "GenomicVariantModel"
    model_uri = f"runs:/{run_id}/model"

    try:
        logger.info(f"📦 Enregistrement du modèle dans le Model Registry sous le nom : '{model_name}'")
        # Enregistre le modèle (crée une nouvelle version à chaque fois que le code tourne)
        model_version = mlflow.register_model(model_uri, model_name)
        
        logger.info(f"🔖 Attribution de l'alias 'Production' à la version {model_version.version}")
        # Assigne l'alias "Production" à cette version spécifique
        client.set_registered_model_alias(
            name=model_name,
            alias="Production",
            version=model_version.version
        )
        logger.info("🎉 Modèle promu en Production avec succès !")
        
    except Exception as e:
        logger.error(f"❌ Échec de la gouvernance du modèle : {e}")

if __name__ == "__main__":
    manage_model()