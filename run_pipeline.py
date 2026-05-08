import os
import sys
import subprocess
import logging
from pathlib import Path

try:
    from prefect import flow, task, get_run_logger
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    def flow(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def task(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def get_run_logger():
        return logging.getLogger("run_pipeline")

# --- CONFIGURATION DU CHEMIN RACINE ---
# Ce fichier étant à la racine, son parent direct est le PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent

# On ajoute le projet au PYTHONPATH pour les imports internes
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.config_utils import ConfigManager

# --- UTILITAIRE DE LANCEMENT SÉCURISÉ ---
def execute_script(script_path):
    """
    Lance un script en injectant le PYTHONPATH correct et en forçant 
    l'exécution depuis la racine du projet (Critique pour Prefect).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    
    # Exécution du sous-processus avec le même Python que Prefect (.venv)
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script_path)], 
        env=env,
        cwd=str(PROJECT_ROOT),  # <-- LA CORRECTION MAGIQUE ICI
        text=True,
        capture_output=True,
    )
    
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise Exception(f"Le script {script_path} a échoué avec le code erreur : {result.returncode}.")
    if result.stdout:
        print(result.stdout)
    return True


def execute_command(command):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        command,
        env=env,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    if result.stdout:
        print(result.stdout)
    return True

# --- 1. TÂCHE : RÉCUPÉRATION DES DONNÉES (DVC) ---
@task(name="Data-Pull-DVC")
def pull_data(cm: ConfigManager, force: bool = False):
    logger = get_run_logger()
    raw_dir = cm.get_path("paths.data.raw_dir")
    model_ready = cm.get_path("paths.data.model_ready")
    final_training = cm.get_path("paths.data.final_training")
    
    if not force and (final_training.exists() or model_ready.exists() or any(raw_dir.glob("*.gz"))):
        logger.info("✅ Données déjà présentes localement.")
        return

    try:
        logger.info("📡 Synchronisation des données depuis S3 via DVC...")
        execute_command(["dvc", "pull", "-f"])
    except FileNotFoundError as exc:
        raise RuntimeError("DVC is not installed. Install requirements with dvc-s3 support.") from exc
    except RuntimeError:
        logger.error("❌ Synchronisation DVC échouée.")
        raise

# --- 2. TÂCHE : ASSEMBLAGE (STITCHING) ---
@task(name="Data-Stitching")
def run_stitching(cm: ConfigManager):
    logger = get_run_logger()
    output_path = cm.get_path("paths.data.model_ready")
    
    if output_path.exists():
        logger.info(f"⏩ Fichier {output_path.name} déjà présent. Skip.")
        return
    logger.info("🧬 Lancement de l'assemblage des chromosomes...")
    execute_script("src/data/Stitching_chr.py")

# --- 3. TÂCHE : ENCODAGE ---
@task(name="Feature-Encoding")
def run_encoding(cm: ConfigManager):
    logger = get_run_logger()
    output_path = cm.get_path("paths.data.final_training")
    
    if output_path.exists():
        logger.info(f"⏩ Fichier {output_path.name} déjà présent. Skip.")
        return
    logger.info("🔢 Lancement de l'encodage des features...")
    execute_script("src/features/encode_features.py")

# --- 4. TÂCHE : ENTRAÎNEMENT ---
@task(name="Model-Training-XGBoost")
def run_training(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("⚡ Lancement de l'entraînement XGBoost...")
    execute_script("src/model/train_model.py")

# --- 5. TÂCHE : VALIDATION CROISÉE ---
@task(name="Model-Cross-Validation")
def run_evaluation(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🧪 Lancement de la 5-Fold Cross Validation...")
    execute_script("src/model/eval.py")

# --- 6. TÂCHE : INTERPRÉTATION ---
@task(name="Model-Interpretation-SHAP")
def run_interpretation(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🧠 Lancement de l'interprétation SHAP...")
    execute_script("src/model/interpret.py")

# --- 7. TÂCHE : GOUVERNANCE (MANAGER) ---
@task(name="Model-Governance")
def run_governance(cm: ConfigManager):
    logger = get_run_logger()
    logger.info("🏛️ Vérification des règles de gouvernance et promotion MLflow...")
    execute_script("src/model/manager.py")

# --- FLUX PRINCIPAL (FLOW) ---
@flow(name="Genomic-Variant-MLOps-Pipeline")
def genomic_mlops_pipeline(force_data_pull: bool = False):
    """Orchestration de la pipeline complète de classification génomique."""
    cm = ConfigManager(project_root=PROJECT_ROOT)
    
    # Exécution séquentielle des tâches
    pull_data(cm, force=force_data_pull)
    run_stitching(cm)
    run_encoding(cm)
    run_training(cm)
    run_evaluation(cm)
    run_interpretation(cm)
    run_governance(cm)

if __name__ == "__main__":
    # Lancement du pipeline
    genomic_mlops_pipeline(force_data_pull=False)
