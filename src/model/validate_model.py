"""
Validate model performance before promotion.
Checks if F1 score meets threshold (>0.75).
"""

import mlflow
import os
import sys

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "file:///home/badr/genomic-variant-mlops/mlruns"))

def validate_model():
    """Validate best model's performance against thresholds."""
    
    # Get best model
    runs = mlflow.search_runs(order_by=["metrics.f1 DESC"], max_results=1)
    
    if not runs:
        print("❌ No model runs found")
        sys.exit(1)
    
    best_run = runs[0]
    metrics = best_run.data.metrics
    
    f1 = metrics.get("f1", 0)
    accuracy = metrics.get("accuracy", 0)
    roc_auc = metrics.get("roc_auc", 0)
    
    print("Model Performance:")
    print(f"  F1 Score: {f1:.4f}")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    
    # Validation thresholds
    THRESHOLD_F1 = 0.75
    
    if f1 < THRESHOLD_F1:
        print(f"\nWarning: F1 score {f1:.4f} below threshold {THRESHOLD_F1}")
        sys.exit(1)
    
    print("\nValidation passed!")
    return True


if __name__ == "__main__":
    validate_model()
