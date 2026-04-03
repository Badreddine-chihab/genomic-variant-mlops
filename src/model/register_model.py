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
from mlflow.entities import MetricHistory
from datetime import datetime

# MLflow tracking URI
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:///home/badr/genomic-variant-mlops/mlruns")
mlflow.set_tracking_uri(TRACKING_URI)

def get_best_run(metric_name="f1", ascending=False):
    """Find the best run across all experiments by metric."""
    all_runs = []
    
    # Iterate through all experiments
    for exp in mlflow.search_experiments():
        runs = mlflow.search_runs(
            experiment_ids=[exp.experiment_id],
            order_by=[f"metrics.{metric_name} {'DESC' if not ascending else 'ASC'}"]
        )
        all_runs.extend(runs)
    
    if not all_runs:
        raise ValueError(f"No runs found with metric '{metric_name}'")
    
    # Sort by metric and return best
    best_run = sorted(
        all_runs, 
        key=lambda x: x.data.metrics.get(metric_name, 0),
        reverse=(not ascending)
    )[0]
    
    return best_run


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
        
        # Transition to stage
        client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)
        client.transition_model_version_stage(
            name=model_name,
            version=model_version.version,
            stage=stage,
            description=description
        )
        
        print(f"✅ Model transitioned to: {stage}")
        
        # Log metrics
        metrics = run.data.metrics
        print(f"\n📊 Model Metrics:")
        for metric_name, value in sorted(metrics.items()):
            print(f"   {metric_name}: {value:.4f}")
        
        return model_version
        
    except mlflow.exceptions.RestException as e:
        if "already exists" in str(e):
            print(f"⚠️  Model '{model_name}' already exists. Creating new version...")
            # Get latest version
            client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)
            versions = client.search_model_versions(f"name='{model_name}'")
            if versions:
                latest = max(versions, key=lambda x: x.version)
                print(f"   Latest version: v{latest.version} in stage '{latest.current_stage}'")
        raise


def main():
    print("=" * 60)
    print("MLflow Model Registry - Register Best Model")
    print("=" * 60)
    
    try:
        # Find best model by F1 score
        best_run = get_best_run(metric_name="f1", ascending=False)
        
        print(f"\n🏆 Best Run Found:")
        print(f"   Run ID: {best_run.info.run_id}")
        print(f"   F1 Score: {best_run.data.metrics.get('f1', 'N/A'):.4f}")
        print(f"   Accuracy: {best_run.data.metrics.get('accuracy', 'N/A'):.4f}")
        print(f"   ROC-AUC: {best_run.data.metrics.get('roc_auc', 'N/A'):.4f}")
        
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
