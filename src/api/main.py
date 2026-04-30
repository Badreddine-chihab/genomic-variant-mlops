import sys
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import mlflow
import pandas as pd
import numpy as np

# --- FIX : Résolution de chemin ---
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.config_utils import ConfigManager
from src.ui.scripts.bridge import fetch_features_from_s3

# Configuration du logger pour le terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cm = ConfigManager(project_root=PROJECT_ROOT)
cfg = cm.config

app = FastAPI(title="Genomic Variant API", description="API de prédiction de pathogénicité")

# ============================================================
# CORS Configuration for React Frontend
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Pydantic Models for Request/Response Validation
# ============================================================
class VariantInput(BaseModel):
    """Input model for variant prediction"""
    chrom: str = Field(..., description="Chromosome (1-22, X, Y)")
    pos: str = Field(..., description="Position (1-based)")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    sift: Optional[float] = Field(None, ge=0, le=1, description="SIFT score")
    polyphen: Optional[float] = Field(None, ge=0, le=1, description="PolyPhen score")
    cadd: Optional[float] = Field(None, ge=0, le=60, description="CADD Phred score")
    alt_freq: Optional[float] = Field(None, ge=0, le=1, description="Allele frequency")

class PredictionResponse(BaseModel):
    """Response model for predictions"""
    status: str
    prediction: int
    probability: Optional[float] = None
    confidence_score: Optional[float] = None
    mutation_type: Optional[str] = None
    cadd_score: Optional[float] = None
    message: Optional[str] = None

class S3FeaturesResponse(BaseModel):
    """Response model for S3 features"""
    found: bool
    data: List[Dict[str, Any]] = []
    message: Optional[str] = None

class HealthResponse(BaseModel):
    """Response model for health check"""
    api_status: str
    model_status: str
    model_uri: Optional[str] = None

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

@app.get("/", response_model=HealthResponse)
def health():
    """API health check endpoint."""
    return {
        "api_status": "online", 
        "model_status": MODEL_STATUS,
        "model_uri": model_uri if MODEL_STATUS == "loaded" else None
    }

@app.get("/api/health", response_model=HealthResponse)
def api_health():
    """Detailed health check endpoint for frontend."""
    return {
        "api_status": "online", 
        "model_status": MODEL_STATUS,
        "model_uri": model_uri if MODEL_STATUS == "loaded" else None
    }

@app.post("/predict", response_model=PredictionResponse)
def predict(data: dict):
    """Legacy prediction endpoint (backward compatible)."""
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

@app.post("/api/predict", response_model=PredictionResponse)
def predict_enhanced(variant: VariantInput):
    """
    Enhanced prediction endpoint for React frontend.
    Returns prediction with confidence scores and metadata.
    """
    if model is None:
        raise HTTPException(
            status_code=503, 
            detail="Model could not be loaded."
        )
    
    try:
        # Convert Pydantic model to dict
        data = variant.dict(exclude_none=True)
        
        # Convert to DataFrame
        df = pd.DataFrame([data])
        
        # Convert categorical columns
        cat_cols = cfg.features.categorical_cols
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype('category')
        
        # Make prediction
        pred = model.predict(df)
        prediction = int(pred[0])
        
        # Try to get prediction probability if available
        probability = None
        confidence_score = None
        try:
            if hasattr(model, 'predict_proba'):
                probas = model.predict_proba(df)
                probability = float(probas[0][1])  # Probability of pathogenic class
                confidence_score = max(probas[0])  # Max probability
        except Exception as e:
            logger.warning(f"Could not get probability: {e}")
        
        logger.info(f"Prediction for {variant.chrom}:{variant.pos} {variant.ref}/{variant.alt} = {prediction}")
        
        return PredictionResponse(
            status="success",
            prediction=prediction,
            probability=probability,
            confidence_score=confidence_score or 0.5,
            cadd_score=variant.cadd,
            mutation_type=None
        )
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Prediction error: {str(e)}"
        )

@app.get("/api/fetch-features", response_model=S3FeaturesResponse)
def fetch_features(chrom: str, pos: str):
    """
    Fetch variant features from S3 feature store using bridge script.
    
    Parameters:
    - chrom: Chromosome number (1-22, X, Y)
    - pos: Position (1-based)
    
    Returns:
    - found: Boolean indicating if variant was found
    - data: List of feature dictionaries
    """
    try:
        logger.info(f"Fetching features for chr{chrom}:{pos}")
        
        # Call bridge function to fetch from S3
        df = fetch_features_from_s3(chrom, pos)
        
        if df is None or df.empty:
            logger.warning(f"Variant not found: chr{chrom}:{pos}")
            return S3FeaturesResponse(
                found=False,
                data=[],
                message=f"Variant chr{chrom}:{pos} not found in S3 feature store"
            )
        
        # Convert DataFrame to list of dicts
        features_list = df.to_dict('records')
        logger.info(f"Found {len(features_list)} records for chr{chrom}:{pos}")
        
        return S3FeaturesResponse(
            found=True,
            data=features_list,
            message=f"Successfully fetched {len(features_list)} record(s)"
        )
    
    except Exception as e:
        logger.error(f"Error fetching features from S3: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Error fetching features: {str(e)}"
        )

@app.get("/api/model-info")
def model_info():
    """
    Get model metadata and information.
    """
    return {
        "status": "success",
        "model_name": "GenomicVariantModel",
        "model_status": MODEL_STATUS,
        "model_uri": model_uri if MODEL_STATUS == "loaded" else None,
        "version": "1.0",
        "description": "XGBoost classifier for genomic variant pathogenicity prediction",
        "input_features": cfg.features.ordered_features if hasattr(cfg.features, 'ordered_features') else [],
        "classes": ["Benign", "Pathogenic"],
    }