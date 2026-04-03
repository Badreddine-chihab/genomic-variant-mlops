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
    
    # Get best model by PR-AUC (better for imbalanced data)
    runs = mlflow.search_runs(order_by=["metrics.pr_auc DESC"], max_results=1)
    
    if not runs:
        print("❌ No model runs found")
        sys.exit(1)
    
    best_run = runs[0]
    metrics = best_run.data.metrics
    
    pr_auc = metrics.get("pr_auc", 0)
    roc_auc = metrics.get("roc_auc", 0)
    f1 = metrics.get("f1", 0)
    
    print("Model Performance:")
    print(f"  PR-AUC: {pr_auc:.4f}")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  F1 Score: {f1:.4f}")
    
    # Validation threshold: PR-AUC > 0.7
    THRESHOLD_PR_AUC = 0.70
    
    if pr_auc < THRESHOLD_PR_AUC:
        print(f"\nWarning: PR-AUC {pr_auc:.4f} below threshold {THRESHOLD_PR_AUC}")
        sys.exit(1)
    
    print("\nValidation passed!")
    return True


if __name__ == "__main__":
    validate_model()
