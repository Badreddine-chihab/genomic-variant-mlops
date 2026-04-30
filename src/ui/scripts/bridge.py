import os
import duckdb
import pandas as pd
import mlflow

def get_s3_connection():
    """Établit la connexion DuckDB avec les credentials AWS (Docker ou Local)."""
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    
    # Récupération des variables d'environnement injectées par Docker
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
        con.execute("INSTALL aws; LOAD aws;")
        con.execute("CALL load_aws_credentials();")
        con.execute(f"SET s3_region='{region}';")
        
    return con

def fetch_features_from_s3(chrom, pos, ref, alt):
    """Interroge le Feature Store sur S3 via DuckDB."""
    # Chemin basé sur ton partitionnement Hive par chromosome
    s3_path = f"s3://aws-s3-bucket-pfa-genomic-classification/data/parquet/chr={chrom}/data.parquet"
    
    try:
        con = get_s3_connection()
        
        # Requête optimisée avec Predicate Pushdown
        # Note : On retire les ' ' autour de {pos} si c'est un entier dans ton Parquet
        query = f"""
            SELECT * FROM read_parquet('{s3_path}') 
            WHERE "pos(1-based)" = {pos}
              AND "ref" = '{ref}'
              AND "alt" = '{alt}'
            LIMIT 1
        """
        
        df = con.execute(query).df()
        return df
    except Exception as e:
        print(f"❌ Erreur lors de la récupération S3 : {e}")
        return None

def predict_variant(model_input_df):
    """Charge le modèle depuis MLflow et effectue la prédiction."""
    try:
        # L'URI utilise le nom du service 'mlflow' défini dans docker-compose
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(tracking_uri)
        
        # Remplace par ton model_name exact ou ton alias
        model_name = "genopredict_xgboost" 
        model_version = "latest"
        
        model = mlflow.pyfunc.load_model(f"models:/{model_name}/{model_version}")
        prediction = model.predict(model_input_df)
        return prediction
    except Exception as e:
        print(f"❌ Erreur de prédiction MLflow : {e}")
        return None