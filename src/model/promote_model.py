"""
Promote best staging model to Production stage in MLflow registry.
"""

import mlflow
import os
import sys

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "file:///home/badr/genomic-variant-mlops/mlruns"))


def promote_to_production():
    """Promote best staging model to production."""
    
    client = mlflow.tracking.MlflowClient()
    model_name = "genomic-variant-classifier"
    
    try:
        # Get all versions of the model
        model_versions = client.search_model_versions(f"name='{model_name}'")
        
        if not model_versions:
            print(f"No model versions found for '{model_name}'")
            return False
        
        # Find latest Staging version
        staging_versions = [mv for mv in model_versions if mv.current_stage == "Staging"]
        
        if not staging_versions:
            print(f"No models in Staging stage")
            return False
        
        latest_staging = max(staging_versions, key=lambda x: int(x.version))
        
        print(f"Found Staging model: v{latest_staging.version}")
        
        # Transition to Production
        client.transition_model_version_stage(
            name=model_name,
            version=latest_staging.version,
            stage="Production",
            archive_existing_versions=True  # Archive old production models
        )
        
        print(f"Successfully promoted v{latest_staging.version} to Production!")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = promote_to_production()
    sys.exit(0 if success else 1)
