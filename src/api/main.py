import sys
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
import mlflow
import pandas as pd

# --- FIX : Résolution de chemin ---
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.config_utils import ConfigManager

# Configuration du logger pour le terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cm = ConfigManager(project_root=PROJECT_ROOT)
cfg = cm.config

app = FastAPI(title="Genomic Variant API", description="API de prédiction de pathogénicité")

# 1. Forcer MLflow à lire dans la base SQLite
tracking_uri = cfg.mlflow.tracking_uri
logger.info(f"📡 Connexion au Model Registry via : {tracking_uri}")
mlflow.set_tracking_uri(tracking_uri)

# 2. Chargement du modèle au démarrage de l'API
try:
    # On utilise le nom exact sous lequel manager.py a enregistré le modèle
    model_name = "GenomicVariantModel"
    model_uri = f"models:/{model_name}@Production"
    
    logger.info(f"⏳ Chargement du modèle depuis : {model_uri}")
    model = mlflow.pyfunc.load_model(model_uri)
    MODEL_STATUS = "loaded"
    logger.info("✅ Modèle 'Production' chargé avec succès en mémoire.")
except Exception as e:
    logger.error(f"❌ Erreur critique lors du chargement du modèle : {e}")
    model = None
    MODEL_STATUS = "not_loaded"

@app.get("/")
def health():
    """Route de vérification de l'état de l'API."""
    return {
        "api_status": "online", 
        "model_status": MODEL_STATUS,
        "model_uri": model_uri if MODEL_STATUS == "loaded" else "none"
    }

@app.post("/predict")
def predict(data: dict):
    """Route principale pour effectuer une prédiction."""
    if model is None:
        raise HTTPException(
            status_code=503, 
            detail="Le modèle n'a pas pu être chargé."
        )
    
    try:
        # 1. Conversion en DataFrame
        df = pd.DataFrame([data])
        
        # ---------------------------------------------------------
        # 🔧 FIX : Conversion des types 'object' en 'category'
        # On utilise la même liste que lors de l'entraînement
        # ---------------------------------------------------------
        cat_cols = cfg.features.categorical_cols
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype('category')
        # ---------------------------------------------------------
        
        # 2. Prédiction
        pred = model.predict(df)
        
        return {
            "status": "success",
            "prediction": int(pred[0])
        }
    except Exception as e:
        logger.error(f"⚠️ Erreur de prédiction avec les données : {data}. Détail: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Erreur lors du traitement de la prédiction : {str(e)}"
        )