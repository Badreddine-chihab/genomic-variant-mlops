import os
import sys
import subprocess
from pathlib import Path
from prefect import flow, task, get_run_logger

# --- CONFIGURATION DU CHEMIN RACINE ---
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.config_utils import ConfigManager

# --- UTILITAIRE POUR LANCER LES SCRIPTS SANS ERREUR D'IMPORT ---
def execute_script(script_path):
    """Lance un script en injectant le PYTHONPATH correct."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / script_path)], env=env)
    if result.returncode != 0:
        raise Exception(f"Le script {script_path} a échoué.")
    return True

# --- 1. TÂCHE : RÉCUPÉRATION DES DONNÉES (DVC) ---
@task(name="DVC-Data-Pull")
def pull_data(cm: ConfigManager, force: bool = False):
    logger = get_run_logger()
    raw_dir = cm.get_path("paths.data.raw_dir")
    if force or not any(raw_dir.glob("*.gz")):
        logger.info("📡 Synchronisation S3...")
        os.system("dvc pull -f")
    else:
        logger.info("✅ Données RAW déjà présentes.")

# --- 2. TÂCHE : ASSEMBLAGE (STITCHING) ---
@task(name="Stitching-Chromosomes")
def run_stitching(cm: ConfigManager):
    logger = get_run_logger()
    output_path = cm.get_path("paths.data.model_ready")
    if output_path.exists():
        logger.info(f"⏩ {output_path.name} déjà présent.")
        return
    execute_script("src/data/Stitching_chr.py")

# --- 3. TÂCHE : ENCODAGE ---
@task(name="Feature-Encoding")
def run_encoding(cm: ConfigManager):
    logger = get_run_logger()
    output_path = cm.get_path("paths.data.final_training")
    if output_path.exists():
        logger.info(f"⏩ {output_path.name} déjà présent.")
        return
    execute_script("src/features/encode_features.py")

# --- 4. TÂCHE : ENTRAÎNEMENT (GPU) ---
@task(name="Model-Training-GPU")
def run_training(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("⚡ Lancement de l'entraînement XGBoost sur la RTX 4070...")
    execute_script("src/model/train_model.py")

# --- 5. TÂCHE : VALIDATION CROISÉE (NEW) ---
@task(name="Model-Cross-Validation")
def run_evaluation(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🧪 Lancement de la 5-Fold Cross Validation...")
    # On utilise notre utilitaire pour éviter le ModuleNotFoundError
    execute_script("src/model/eval.py")

@task(name="Model-Interpretation-SHAP")
def run_interpretation(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🧪 Lancement de l'interprétation SHAP...")
    # On utilise notre utilitaire pour éviter le ModuleNotFoundError
    execute_script("src/model/interpret.py")


# Dans run_pipeline.py

@task(name="Model-Governance")
def run_governance(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🏛️ Vérification des règles de gouvernance et promotion...")
    # On lance le nouveau script manager.py
    execute_script("src/model/manager.py")

# Dans ton @flow
@flow(name="Genomic-Variant-Pipeline")
def genomic_mlops_pipeline(force_data_pull: bool = False):
    cm = ConfigManager(project_root=PROJECT_ROOT)
    
    pull_data(cm, force=force_data_pull)
    run_stitching(cm)
    run_encoding(cm)
    run_training(cm)
    run_evaluation(cm)
    run_interpretation(cm)
    run_governance(cm) # <-- LA NOUVELLE ÉTAPE UNIQUE

if __name__ == "__main__":
    genomic_mlops_pipeline(force_data_pull=False)