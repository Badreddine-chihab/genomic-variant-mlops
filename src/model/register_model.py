"""
MLflow Model Registry: Register best models for production deployment.

This script:
1. Finds the best run (by F1 score across all experiments)
2. Registers the model to MLflow Model Registry
3. Tags it as 'staging' or 'production'
4. Logs model metadata and lineage
"""

import os
import mlflow
from datetime import datetime

# MLflow tracking URI
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:///home/badr/genomic-variant-mlops/mlruns")
mlflow.set_tracking_uri(TRACKING_URI)

def get_best_run(metric_name="pr_auc", ascending=False):
    """Find the best run across all experiments by metric.
    
    Defaults to PR-AUC which is better for imbalanced genomic variant classification.
    """
    
    # Use MLflow client to search for best run
    client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)
    
    # Get all experiment IDs
    experiments = client.search_experiments()
    experiment_ids = [exp.experiment_id for exp in experiments]
    
    if not experiment_ids:
        raise ValueError("No experiments found")
    
    # Search all runs across all experiments, ordered by metric
    runs = client.search_runs(
        experiment_ids=experiment_ids,
        order_by=[f"metrics.{metric_name} {'ASC' if ascending else 'DESC'}"],
        max_results=1
    )
    
    if not runs:
        raise ValueError(f"No runs found with metric '{metric_name}'")
    
    return runs[0]


def register_model_to_registry(run, model_name, stage="Staging", description=""):
    """Register a model from MLflow run to Model Registry."""
    
    # Get run details
    run_id = run.info.run_id
    experiment_id = run.info.experiment_id
    
    model_uri = f"runs:/{run_id}/model"
    
    print(f"\n📦 Registering model from Run: {run_id}")
    print(f"   Experiment: {experiment_id}")
    print(f"   Model URI: {model_uri}")
    
    # Register model
    try:
        model_version = mlflow.register_model(
            model_uri=model_uri,
            name=model_name,
            tags={
                "run_id": run_id,
                "experiment_id": str(experiment_id),
                "registered_at": datetime.now().isoformat(),
                "source": "genomic-variant-mlops"
            }
        )
        
        print(f"✅ Model registered: {model_name} (v{model_version.version})")
        
        # Transition to stage (note: stages are deprecated in MLflow 2.9+)
        client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)
        try:
            client.transition_model_version_stage(
                name=model_name,
                version=model_version.version,
                stage=stage
            )
            print(f"✅ Model transitioned to: {stage}")
        except Exception as stage_error:
            print(f"⚠️  Could not transition stage: {stage_error}")
        
        print(f"\n📊 Model Successfully Registered!")
        print(f"   PR-AUC: {run.data.metrics.get('pr_auc', 'N/A'):.4f}")
        print(f"   ROC-AUC: {run.data.metrics.get('roc_auc', 'N/A'):.4f}")
        
        return model_version
        
    except mlflow.exceptions.RestException as e:
        if "already exists" in str(e):
            print(f"⚠️  Model '{model_name}' already exists. Version already created.")
            client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)
            versions = client.search_model_versions(f"name='{model_name}'")
            if versions:
                latest = max(versions, key=lambda x: int(x.version))
                print(f"   Latest version: v{latest.version}")
        raise


def main():
    print("=" * 60)
    print("MLflow Model Registry - Register Best Model")
    print("=" * 60)
    
    try:
        # Find best model by PR-AUC score (better for imbalanced data)
        best_run = get_best_run(metric_name="pr_auc", ascending=False)
        
        print(f"\n🏆 Best Run Found:")
        print(f"   Run ID: {best_run.info.run_id}")
        if hasattr(best_run, 'data') and hasattr(best_run.data, 'metrics'):
            print(f"   PR-AUC: {best_run.data.metrics.get('pr_auc', 'N/A'):.4f}")
            print(f"   ROC-AUC: {best_run.data.metrics.get('roc_auc', 'N/A'):.4f}")
            print(f"   F1 Score: {best_run.data.metrics.get('f1', 'N/A'):.4f}")
        
        # Register to Model Registry
        model_version = register_model_to_registry(
            run=best_run,
            model_name="genomic-variant-classifier",
            stage="Staging",
            description="XGBoost classifier for pathogenic vs benign variant classification"
        )
        
        print(f"\n✨ Model successfully registered to MLflow Model Registry!")
        print(f"   Name: genomic-variant-classifier")
        print(f"   Version: {model_version.version}")
        print(f"   Stage: Staging")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
