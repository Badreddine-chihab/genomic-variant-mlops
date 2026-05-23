import sys
import os
import logging
import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import mlflow
import mlflow.xgboost
import pandas as pd
import numpy as np

# --- FIX : Résolution de chemin ---
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.config_utils import ConfigManager
from src.features.schema_contract import FEATURE_ORDER, enforce_feature_contract
from src.features.encode_features import CHR_LENGTHS, TRANSITIONS, TRANVERSIONS
from src.monitoring.prediction_logger import (
    load_prediction_events,
    log_prediction_event,
    summarize_predictions,
)
from src.monitoring.prometheus_metrics import (
    observe_feature_lookup,
    observe_prediction,
    observe_vcf_batch_records,
    render_metrics,
    set_model_loaded,
)

# Configuration du logger pour le terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
HAS_MULTIPART = importlib.util.find_spec("multipart") is not None
LOCAL_FEATURE_STORE_PATH = Path(
    os.getenv(
        "GENOPREDICT_FEATURE_STORE_PATH",
        PROJECT_ROOT / "data" / "processed" / "model_ready_dataset.parquet",
    )
)
DRIFT_SUMMARY_PATH = Path(
    os.getenv(
        "GENOPREDICT_DRIFT_SUMMARY_PATH",
        PROJECT_ROOT / "reports" / "monitoring" / "latest_drift_summary.json",
    )
)
_LOCAL_FEATURE_CACHE: Dict[str, Any] = {"path": None, "mtime": None, "df": None}

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

class VCFUploadResponse(BaseModel):
    """Response model for VCF preview upload."""
    found: bool
    records: List[Dict[str, Any]] = []
    total_records: int = 0
    message: Optional[str] = None

class VCFVariantInput(BaseModel):
    chrom: str
    pos: str
    ref: str
    alt: str

class VCFBatchPredictRequest(BaseModel):
    records: List[VCFVariantInput]
    max_records: int = 200

class VCFBatchPredictItem(BaseModel):
    chrom: str
    pos: str
    ref: str
    alt: str
    found_in_store: bool
    status: str
    prediction: Optional[int] = None
    label: Optional[str] = None
    probability: Optional[float] = None
    confidence_score: Optional[float] = None
    message: Optional[str] = None

class VCFBatchPredictResponse(BaseModel):
    status: str
    total_input: int
    processed: int
    predicted: int
    not_found: int
    failed: int
    results: List[VCFBatchPredictItem]

class HealthResponse(BaseModel):
    """Response model for health check"""
    api_status: str
    model_status: str
    model_uri: Optional[str] = None

# 1. Tracking URI (env override for container deployments)
tracking_uri = os.getenv("MLFLOW_TRACKING_URI", cfg.mlflow.tracking_uri)
logger.info(f"📡 Connexion au Model Registry via : {tracking_uri}")
mlflow.set_tracking_uri(tracking_uri)

# 2. Chargement du modèle au démarrage de l'API
try:
    # On utilise le nom exact sous lequel manager.py a enregistré le modèle
    model_name = "GenomicVariantModel"
    model_uri = f"models:/{model_name}@Production"
    
    logger.info(f"⏳ Chargement du modèle depuis : {model_uri}")
    model = mlflow.pyfunc.load_model(model_uri)
    model_xgb = None
    try:
        model_xgb = mlflow.xgboost.load_model(model_uri)
    except Exception as xgb_load_error:
        logger.warning(f"⚠️ Could not load xgboost flavor model for probabilities: {xgb_load_error}")
    MODEL_STATUS = "loaded"
    logger.info("✅ Modèle 'Production' chargé avec succès en mémoire.")
except Exception as e:
    logger.error(f"❌ Erreur critique lors du chargement du modèle : {e}")
    model = None
    model_xgb = None
    MODEL_STATUS = "not_loaded"

    fallback_model_path = PROJECT_ROOT / "src" / "model" / "xgboost_gpu_model.json"
    if fallback_model_path.exists():
        try:
            import xgboost as xgb

            logger.info(f"↩️ Loading local fallback model from: {fallback_model_path}")
            fallback_model = xgb.XGBClassifier()
            fallback_model.load_model(str(fallback_model_path))
            model = fallback_model
            model_xgb = fallback_model
            model_uri = str(fallback_model_path)
            MODEL_STATUS = "loaded_local_fallback"
            logger.info("✅ Local fallback model loaded successfully.")
        except Exception as fallback_error:
            logger.error(f"❌ Local fallback model could not be loaded: {fallback_error}")

set_model_loaded(MODEL_STATUS in {"loaded", "loaded_local_fallback"})


def _active_model_uri() -> Optional[str]:
    return model_uri if MODEL_STATUS in {"loaded", "loaded_local_fallback"} else None


def _predict_with_probability(df: pd.DataFrame) -> tuple[int, Optional[float], float]:
    raw_pred = model.predict(df)
    prediction = int(np.ravel(raw_pred)[0])

    probability: Optional[float] = None
    confidence = 0.5

    # First try through pyfunc wrapper.
    try:
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(df)
            probability = float(proba[0][1]) if np.ndim(proba) > 1 else float(proba[0])
    except Exception as e:
        logger.warning(f"Could not get probability from pyfunc model: {e}")

    # Fallback to native xgboost flavor.
    if probability is None and model_xgb is not None:
        try:
            if hasattr(model_xgb, "predict_proba"):
                proba = model_xgb.predict_proba(df)
                probability = float(proba[0][1]) if np.ndim(proba) > 1 else float(proba[0])
            elif hasattr(model_xgb, "predict"):
                xgb_raw = np.ravel(model_xgb.predict(df))
                if xgb_raw.size:
                    candidate = float(xgb_raw[0])
                    if 0.0 <= candidate <= 1.0:
                        probability = candidate
        except Exception as e:
            logger.warning(f"Could not get probability from xgboost flavor: {e}")

    if probability is not None:
        probability = max(0.0, min(1.0, probability))
        confidence = max(probability, 1.0 - probability)

    return prediction, probability, confidence


def _normalize_chrom(value: Any) -> str:
    chrom = str(value).strip()
    return chrom[3:] if chrom.lower().startswith("chr") else chrom.upper()


def _variant_to_predict_payload(row: Dict[str, Any], chrom: str, pos: str, ref: str, alt: str) -> Dict[str, Any]:
    def _num(*keys: str) -> Optional[float]:
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except Exception:
                continue
        return None

    payload = {
        "chrom": str(chrom),
        "pos": str(pos),
        "ref": str(ref).upper(),
        "alt": str(alt).upper(),
    }

    sift = _num("SIFT_score", "SIFT")
    polyphen = _num("Polyphen2_HVAR_score", "Polyphen2_HDIV_score", "PolyPhen")
    cadd = _num("CADD_phred", "CADD")
    alt_freq = _num("gnomAD_exomes_AF", "ALT_FREQ")

    if sift is not None:
        payload["sift"] = sift
    if polyphen is not None:
        payload["polyphen"] = polyphen
    if cadd is not None:
        payload["cadd"] = cadd
    if alt_freq is not None:
        payload["alt_freq"] = alt_freq

    return payload


def _build_model_features(payload: Dict[str, Any]) -> Dict[str, Any]:
    def _num(default: float, *keys: str) -> float:
        for key in keys:
            value = payload.get(key)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except Exception:
                continue
        return default

    chrom = _normalize_chrom(payload.get("chrom", payload.get("CHROM", "1")))
    pos = _num(0.0, "pos", "POS", "pos(1-based)")
    ref = str(payload.get("ref", payload.get("REF", "N")) or "N").upper()
    alt = str(payload.get("alt", payload.get("ALT", "N")) or "N").upper()
    sift = _num(-1.0, "sift", "SIFT", "SIFT_score")
    polyphen = _num(-1.0, "polyphen", "PolyPhen", "Polyphen2_HVAR_score", "Polyphen2_HDIV_score")
    cadd = _num(-1.0, "cadd", "CADD", "CADD_phred")
    alt_freq = _num(0.0, "alt_freq", "ALT_FREQ", "gnomAD_exomes_AF")

    ref_base = ref[:1] or "N"
    alt_base_raw = alt[:1] or "N"
    is_indel = int(len(ref) != len(alt))
    delta_length = len(alt) - len(ref)
    indel_size = abs(delta_length)
    is_frameshift = int(is_indel == 1 and indel_size % 3 != 0)
    alt_base = "-" if is_indel else alt_base_raw
    mutation_type = "INDEL" if is_indel else f"{ref_base}_{alt_base}"
    rare_variant = int(alt_freq < 0.005)
    is_ultra_rare = int(alt_freq < 0.001)
    is_large_indel = int(indel_size > 5)
    cadd_high = int(cadd > 20)
    cadd_very_high = int(cadd > 30)
    sift_damaging = int(sift >= 0 and sift < 0.05)
    polyphen_damaging = int(polyphen > 0.85)
    impact_score = (
        is_frameshift * 3.0
        + is_large_indel * 2.0
        + indel_size * 0.1
        + is_ultra_rare * 2.0
        + cadd_high * 2.0
    )
    chr_length = float(CHR_LENGTHS.get(chrom, CHR_LENGTHS["1"]))
    normalized_pos = max(0.0, min(1.0, pos / chr_length if chr_length else 0.0))

    return {
        "CHROM": chrom,
        "SIFT": sift,
        "PolyPhen": polyphen,
        "CADD": cadd,
        "ALT_FREQ": alt_freq,
        "Is_InDel": is_indel,
        "Delta_Length": delta_length,
        "indel_size": indel_size,
        "Is_Frameshift": is_frameshift,
        "REF_Base": ref_base,
        "ALT_Base": alt_base,
        "mutation_type": mutation_type,
        "freq_log": float(np.log1p(alt_freq)),
        "rare_variant": rare_variant,
        "is_ultra_rare": is_ultra_rare,
        "is_large_indel": is_large_indel,
        "CADD_high": cadd_high,
        "CADD_very_high": cadd_very_high,
        "SIFT_damaging": sift_damaging,
        "PolyPhen_damaging": polyphen_damaging,
        "CADD_x_rare": cadd * rare_variant,
        "Impact_Score": impact_score,
        "rare_impact": rare_variant * impact_score,
        "normalized_pos": normalized_pos,
        "pos_bin": int(max(0, min(9, np.floor(normalized_pos * 10)))),
        "pos_freq_interaction": normalized_pos * alt_freq,
        "is_transition": int(mutation_type in TRANSITIONS),
        "is_transversion": int(mutation_type in TRANVERSIONS),
        "chrom_freq_mean": 0.0,
        "chrom_rare_rate": 0.0,
    }


def _fetch_features_with_timeout(fetch_fn, chrom: str, pos: str, ref: str, alt: str, timeout_seconds: int = 20):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_fn, chrom, pos, ref, alt)
        return future.result(timeout=timeout_seconds)


def _load_local_feature_store() -> Optional[pd.DataFrame]:
    path = LOCAL_FEATURE_STORE_PATH
    if not path.exists():
        return None

    mtime = path.stat().st_mtime
    if (
        _LOCAL_FEATURE_CACHE["path"] != str(path)
        or _LOCAL_FEATURE_CACHE["mtime"] != mtime
        or _LOCAL_FEATURE_CACHE["df"] is None
    ):
        _LOCAL_FEATURE_CACHE.update(
            {
                "path": str(path),
                "mtime": mtime,
                "df": pd.read_parquet(path),
            }
        )
    return _LOCAL_FEATURE_CACHE["df"]


def _fetch_features_from_local_store(chrom: str, pos: str, ref: str, alt: str) -> Optional[pd.DataFrame]:
    df = _load_local_feature_store()
    if df is None or df.empty:
        return None

    chrom_col = "#chr" if "#chr" in df.columns else "CHROM" if "CHROM" in df.columns else None
    pos_col = "pos(1-based)" if "pos(1-based)" in df.columns else "POS" if "POS" in df.columns else None
    ref_col = "ref" if "ref" in df.columns else "REF" if "REF" in df.columns else None
    alt_col = "alt" if "alt" in df.columns else "ALT" if "ALT" in df.columns else None
    if not all([chrom_col, pos_col, ref_col, alt_col]):
        logger.warning(f"Local feature store {LOCAL_FEATURE_STORE_PATH} is missing variant identity columns.")
        return None

    mask = (
        df[chrom_col].map(_normalize_chrom).eq(_normalize_chrom(chrom))
        & df[pos_col].astype(str).eq(str(pos).strip())
        & df[ref_col].astype(str).str.upper().eq(str(ref).strip().upper())
        & df[alt_col].astype(str).str.upper().eq(str(alt).strip().upper())
    )
    result = df.loc[mask].head(1).copy()
    return result if not result.empty else None


def _fetch_features_from_feature_store(fetch_fn, chrom: str, pos: str, ref: str, alt: str) -> tuple[Optional[pd.DataFrame], str]:
    local_df = _fetch_features_from_local_store(chrom, pos, ref, alt)
    if local_df is not None and not local_df.empty:
        return local_df, f"local feature store ({LOCAL_FEATURE_STORE_PATH})"

    remote_df = _fetch_features_with_timeout(fetch_fn, chrom, pos, ref, alt, timeout_seconds=20)
    if remote_df is not None and not remote_df.empty:
        return remote_df, "S3 feature store"

    return remote_df, "feature store"


def _log_prediction_monitoring(
    endpoint: str,
    source: str,
    payload: Dict[str, Any],
    latency_seconds: float,
    status: str = "success",
    prediction: Optional[int] = None,
    probability: Optional[float] = None,
    confidence_score: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    def _first_present(*keys: str) -> Any:
        for key in keys:
            value = payload.get(key)
            if value is not None and value != "":
                return value
        return None

    event = {
        "endpoint": endpoint,
        "source": source,
        "status": status,
        "model_uri": _active_model_uri(),
        "latency_ms": round(latency_seconds * 1000.0, 3),
        "chrom": _first_present("chrom", "CHROM", "#chr"),
        "pos": _first_present("pos", "POS", "pos(1-based)"),
        "ref": _first_present("ref", "REF"),
        "alt": _first_present("alt", "ALT"),
        "sift": _first_present("sift", "SIFT", "SIFT_score"),
        "polyphen": _first_present("polyphen", "PolyPhen", "Polyphen2_HVAR_score"),
        "cadd": _first_present("cadd", "CADD", "CADD_phred"),
        "alt_freq": _first_present("alt_freq", "ALT_FREQ", "gnomAD_exomes_AF"),
        "prediction": prediction,
        "probability": probability,
        "confidence_score": confidence_score,
        "error": error,
    }

    log_prediction_event(event)
    observe_prediction(
        endpoint=endpoint,
        status=status,
        source=source,
        latency_seconds=latency_seconds,
        prediction=prediction,
        confidence=confidence_score,
    )

@app.get("/", response_model=HealthResponse)
def health():
    """API health check endpoint."""
    return {
        "api_status": "online", 
        "model_status": MODEL_STATUS,
        "model_uri": _active_model_uri()
    }

@app.get("/api/health", response_model=HealthResponse)
def api_health():
    """Detailed health check endpoint for frontend."""
    return {
        "api_status": "online", 
        "model_status": MODEL_STATUS,
        "model_uri": _active_model_uri()
    }

@app.post("/predict", response_model=PredictionResponse)
def predict(data: dict):
    """Legacy prediction endpoint (backward compatible)."""
    if model is None:
        raise HTTPException(
            status_code=503, 
            detail="Le modèle n'a pas pu être chargé."
        )

    start = time.perf_counter()
    try:
        # 1. Conversion en DataFrame
        df = pd.DataFrame([_build_model_features(data)])
        
        df = enforce_feature_contract(df, fill_missing=True)
        
        prediction, probability, confidence = _predict_with_probability(df)

        _log_prediction_monitoring(
            endpoint="/predict",
            source="legacy",
            payload=data,
            latency_seconds=time.perf_counter() - start,
            prediction=prediction,
            probability=probability,
            confidence_score=confidence,
        )

        return {
            "status": "success",
            "prediction": prediction,
            "probability": probability,
            "confidence_score": confidence
        }
    except Exception as e:
        logger.error(f"⚠️ Erreur de prédiction avec les données : {data}. Détail: {e}")
        _log_prediction_monitoring(
            endpoint="/predict",
            source="legacy",
            payload=data,
            latency_seconds=time.perf_counter() - start,
            status="error",
            error=str(e),
        )
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

    start = time.perf_counter()
    data: Dict[str, Any] = variant.model_dump(exclude_none=True)
    try:
        # Convert to DataFrame
        df = pd.DataFrame([_build_model_features(data)])
        
        df = enforce_feature_contract(df, fill_missing=True)
        
        prediction, probability, confidence_score = _predict_with_probability(df)
        
        logger.info(f"Prediction for {variant.chrom}:{variant.pos} {variant.ref}/{variant.alt} = {prediction}")

        _log_prediction_monitoring(
            endpoint="/api/predict",
            source="api",
            payload=data,
            latency_seconds=time.perf_counter() - start,
            prediction=prediction,
            probability=probability,
            confidence_score=confidence_score,
        )
        
        return PredictionResponse(
            status="success",
            prediction=prediction,
            probability=probability,
            confidence_score=confidence_score,
            cadd_score=variant.cadd,
            mutation_type=None
        )
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        _log_prediction_monitoring(
            endpoint="/api/predict",
            source="api",
            payload=data,
            latency_seconds=time.perf_counter() - start,
            status="error",
            error=str(e),
        )
        raise HTTPException(
            status_code=400, 
            detail=f"Prediction error: {str(e)}"
        )

@app.get("/api/fetch-features", response_model=S3FeaturesResponse)
def fetch_features(chrom: str, pos: str, ref: Optional[str] = None, alt: Optional[str] = None):
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
        ref_q = (ref or "").strip().upper()
        alt_q = (alt or "").strip().upper()
        if not ref_q or not alt_q:
            raise HTTPException(
                status_code=422,
                detail="Both ref and alt query params are required for precise feature lookup."
            )

        logger.info(f"Fetching features for chr{chrom}:{pos} {ref_q}>{alt_q}")

        try:
            from src.ui.scripts.bridge import fetch_features_from_s3
        except Exception as import_error:
            raise HTTPException(
                status_code=500,
                detail=f"Feature store dependency missing: {import_error}"
            )

        try:
            df, feature_source = _fetch_features_from_feature_store(fetch_features_from_s3, chrom, pos, ref_q, alt_q)
        except FuturesTimeoutError:
            observe_feature_lookup("timeout")
            raise HTTPException(
                status_code=504,
                detail="Feature store lookup timed out. Please retry."
            )
        
        if df is None or df.empty:
            observe_feature_lookup("not_found")
            logger.warning(f"Variant not found: chr{chrom}:{pos} {ref_q}>{alt_q}")
            return S3FeaturesResponse(
                found=False,
                data=[],
                message=f"Variant chr{chrom}:{pos} {ref_q}>{alt_q} not found in feature store"
            )
        
        # Convert DataFrame to list of dicts
        features_list = df.to_dict('records')
        observe_feature_lookup("found")
        logger.info(f"Found {len(features_list)} records for chr{chrom}:{pos} {ref_q}>{alt_q} in {feature_source}")
        
        return S3FeaturesResponse(
            found=True,
            data=features_list,
            message=f"Successfully fetched {len(features_list)} record(s) from {feature_source}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        observe_feature_lookup("error")
        logger.error(f"Error fetching features from S3: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Error fetching features: {str(e)}"
        )

def _parse_vcf_content(content: bytes, limit: int) -> VCFUploadResponse:
    text = content.decode("utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue

        chrom, pos, _id, ref, alt = parts[:5]
        # ALT can be comma-separated; keep one row per ALT for usability.
        for alt_allele in alt.split(","):
            alt_allele = alt_allele.strip().upper()
            if not alt_allele:
                continue
            rows.append(
                {
                    "chrom": chrom.replace("chr", "").upper(),
                    "pos": pos,
                    "ref": ref.upper(),
                    "alt": alt_allele,
                }
            )
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break

    if not rows:
        return VCFUploadResponse(
            found=False,
            records=[],
            total_records=0,
            message="No valid VCF records found."
        )

    return VCFUploadResponse(
        found=True,
        records=rows,
        total_records=len(rows),
        message=f"Parsed {len(rows)} variant records from VCF."
    )


if HAS_MULTIPART:
    @app.post("/api/upload-vcf", response_model=VCFUploadResponse)
    async def upload_vcf(file: UploadFile = File(...), limit: int = 200):
        """
        Upload and parse a VCF file to preview variants for downstream scoring.
        Returns a lightweight list with CHROM, POS, REF, ALT.
        """
        filename = (file.filename or "").lower()
        if not (filename.endswith(".vcf") or filename.endswith(".vcf.gz")):
            raise HTTPException(status_code=400, detail="Please upload a .vcf or .vcf.gz file.")

        if limit <= 0 or limit > 5000:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 5000.")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        try:
            return _parse_vcf_content(content, limit)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"VCF parsing error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to parse VCF: {str(e)}")
else:
    @app.post("/api/upload-vcf", response_model=VCFUploadResponse)
    async def upload_vcf(file=None, limit: int = 200):
        if file is None:
            raise HTTPException(
                status_code=503,
                detail="VCF upload requires python-multipart. Install with: pip install python-multipart",
            )
        content = await file.read()
        return _parse_vcf_content(content, limit)


@app.post("/api/vcf-batch-predict", response_model=VCFBatchPredictResponse)
def vcf_batch_predict(request: VCFBatchPredictRequest):
    """
    Batch predict variants parsed from VCF.
    Workflow:
    1) For each record, query feature store using chrom/pos/ref/alt.
    2) Predict only when found in store (no manual fallback in batch mode).
    3) Return per-record statuses and aggregate counters.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model could not be loaded.")

    max_records = max(1, min(5000, int(request.max_records)))
    input_records = request.records[:max_records]
    if not input_records:
        raise HTTPException(status_code=400, detail="No records provided.")

    try:
        from src.ui.scripts.bridge import fetch_features_from_s3
    except Exception as import_error:
        raise HTTPException(
            status_code=500,
            detail=f"Feature store dependency missing: {import_error}"
        )

    results: List[VCFBatchPredictItem] = []
    predicted = 0
    not_found = 0
    failed = 0

    for record in input_records:
        start = time.perf_counter()
        chrom = str(record.chrom).replace("chr", "").upper()
        pos = str(record.pos)
        ref = str(record.ref).upper()
        alt = str(record.alt).upper()
        payload_for_monitoring = {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}

        try:
            try:
                df_store, _feature_source = _fetch_features_from_feature_store(fetch_features_from_s3, chrom, pos, ref, alt)
            except FuturesTimeoutError:
                observe_feature_lookup("timeout")
                observe_vcf_batch_records("failed", 1)
                _log_prediction_monitoring(
                    endpoint="/api/vcf-batch-predict",
                    source="vcf_batch",
                    payload=payload_for_monitoring,
                    latency_seconds=time.perf_counter() - start,
                    status="error",
                    error="Feature store lookup timed out.",
                )
                failed += 1
                results.append(
                    VCFBatchPredictItem(
                        chrom=chrom,
                        pos=pos,
                        ref=ref,
                        alt=alt,
                        found_in_store=False,
                        status="failed",
                        message="Feature store lookup timed out.",
                    )
                )
                continue
            if df_store is None or df_store.empty:
                observe_feature_lookup("not_found")
                observe_vcf_batch_records("not_found", 1)
                not_found += 1
                results.append(
                    VCFBatchPredictItem(
                        chrom=chrom,
                        pos=pos,
                        ref=ref,
                        alt=alt,
                        found_in_store=False,
                        status="not_found",
                        message="Variant not found in feature store.",
                    )
                )
                continue

            observe_feature_lookup("found")
            row = df_store.iloc[0].to_dict()
            payload = _variant_to_predict_payload(row, chrom, pos, ref, alt)
            payload_for_monitoring.update(payload)
            df_pred = enforce_feature_contract(pd.DataFrame([_build_model_features(payload)]), fill_missing=True)
            prediction, probability, confidence = _predict_with_probability(df_pred)
            observe_vcf_batch_records("predicted", 1)
            predicted += 1

            _log_prediction_monitoring(
                endpoint="/api/vcf-batch-predict",
                source="vcf_batch",
                payload=payload_for_monitoring,
                latency_seconds=time.perf_counter() - start,
                prediction=prediction,
                probability=probability,
                confidence_score=confidence,
            )

            results.append(
                VCFBatchPredictItem(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    found_in_store=True,
                    status="predicted",
                    prediction=prediction,
                    label="PATHOGENIC" if prediction == 1 else "BENIGN",
                    probability=probability,
                    confidence_score=confidence,
                )
            )
        except Exception as e:
            observe_vcf_batch_records("failed", 1)
            failed += 1
            logger.error(f"Batch prediction failed for {chrom}:{pos} {ref}>{alt}: {e}")
            _log_prediction_monitoring(
                endpoint="/api/vcf-batch-predict",
                source="vcf_batch",
                payload=payload_for_monitoring,
                latency_seconds=time.perf_counter() - start,
                status="error",
                error=str(e),
            )
            results.append(
                VCFBatchPredictItem(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    found_in_store=False,
                    status="failed",
                    message=str(e),
                )
            )

    return VCFBatchPredictResponse(
        status="success",
        total_input=len(request.records),
        processed=len(input_records),
        predicted=predicted,
        not_found=not_found,
        failed=failed,
        results=results,
    )


@app.get("/metrics")
def metrics():
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@app.get("/api/monitoring/summary")
def monitoring_summary():
    summary = summarize_predictions()
    summary.update(
        {
            "api_status": "online",
            "model_status": MODEL_STATUS,
            "model_uri": _active_model_uri(),
        }
    )
    return summary


@app.get("/api/monitoring/predictions")
def monitoring_predictions(limit: int = 100):
    limit = max(1, min(1000, int(limit)))
    return {"items": load_prediction_events(limit=limit), "limit": limit}


@app.get("/api/monitoring/drift")
def monitoring_drift():
    if not DRIFT_SUMMARY_PATH.exists():
        return {
            "status": "not_available",
            "message": "No drift summary has been generated yet.",
            "summary_path": str(DRIFT_SUMMARY_PATH),
        }

    try:
        return json.loads(DRIFT_SUMMARY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail=f"Drift summary is not valid JSON: {error}")


@app.get("/api/model-info")
def model_info():
    """
    Get model metadata and information.
    """
    return {
        "status": "success",
        "model_name": "GenomicVariantModel",
        "model_status": MODEL_STATUS,
        "model_uri": _active_model_uri(),
        "version": "1.0",
        "description": "XGBoost classifier for genomic variant pathogenicity prediction",
        "input_features": FEATURE_ORDER,
        "classes": ["Benign", "Pathogenic"],
    }
