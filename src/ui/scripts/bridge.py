import os
import duckdb
import pandas as pd
import mlflow
import logging

logger = logging.getLogger(__name__)

def get_s3_connection():
    """Établit la connexion DuckDB avec les credentials AWS (Docker ou Local)."""
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if access_key and secret_key:
        # Mode Docker : Utilise les variables du fichier .env
        con.execute(f"SET s3_access_key_id='{access_key}';")
        con.execute(f"SET s3_secret_access_key='{secret_key}';")
        con.execute(f"SET s3_region='{region}';")
    else:
        # Mode Local/Fallback : Utilise le fichier ~/.aws/credentials
        try:
            con.execute("INSTALL aws; LOAD aws;")
            con.execute("CALL load_aws_credentials();")
            con.execute(f"SET s3_region='{region}';")
        except Exception as e:
            logger.warning(f"⚠️ AWS credentials fallback failed: {e}")
        
    return con

def fetch_features_from_s3(chrom, pos, ref, alt):
    """Interroge le Feature Store sur S3 via DuckDB."""
    s3_bucket = os.getenv("S3_BUCKET", "aws-s3-bucket-pfa-genomic-classification")
    s3_path = f"s3://{s3_bucket}/data/parquet/chr={chrom}/data.parquet"
    
    try:
        con = get_s3_connection()
        
        # Requête optimisée avec Predicate Pushdown
        query = f"""
            SELECT * FROM read_parquet('{s3_path}') 
            WHERE "pos(1-based)" = {pos}
              AND "ref" = '{ref}'
              AND "alt" = '{alt}'
            LIMIT 1
        """
        
        df = con.execute(query).df()
        logger.info(f"✅ Features fetched from S3: {s3_path}")
        return df
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération S3 : {e}")
        return None

def predict_variant(model_input_df):
    """Charge le modèle depuis MLflow et effectue la prédiction."""
    try:
        # L'URI utilise le nom du service 'mlflow' défini dans docker-compose
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(tracking_uri)
        
        # ✅ FIX: Utilise le bon nom de modèle et alias
        model_name = "GenomicVariantModel"
        alias = "Production"
        
        logger.info(f"📦 Chargement du modèle {model_name}@{alias} depuis {tracking_uri}")
        model = mlflow.pyfunc.load_model(f"models:/{model_name}@{alias}")
        
        prediction = model.predict(model_input_df)
        logger.info(f"✅ Prédiction réussie: {prediction}")
        return prediction
        
    except Exception as e:
        logger.error(f"❌ Erreur de prédiction MLflow : {e}")
        return None

def test_s3_connection():
    """Teste la connexion S3 sans récupérer de données."""
    try:
        con = get_s3_connection()
        con.execute("SELECT 1 as test").fetchall()
        logger.info("✅ Connexion S3 réussie!")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur connexion S3 : {e}")
        return False

if __name__ == "__main__":
    # Test basique
    logging.basicConfig(level=logging.INFO)
    test_s3_connection()