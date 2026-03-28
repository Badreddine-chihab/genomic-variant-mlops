import os
import pandas as pd
import numpy as np
import mlflow
from xgboost import XGBClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

def evaluate_model_cv(data_path):
    # 1. Ensure working directory is set to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 2. Setup MLflow Tracking (Using explicit URI to avoid conflicts)
    TRACKING_URI = f"file://{os.path.join(script_dir, 'mlruns')}"
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("genomic-variant-cv-evaluation")

    print(f"Loading data from: {data_path}")
    df = pd.read_parquet(data_path)

    # 3. Prepare Data
    cat_cols = ["CHROM", "REF_Base", "ALT_Base", "mutation_type"]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    target_col = "Target" if "Target" in df.columns else "target"
    if target_col not in df.columns:
        raise KeyError(f"Target column missing! Available columns: {df.columns.tolist()}")

    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Handle class imbalance for the model parameters
    scale_pos_weight = (len(y) - sum(y)) / sum(y)

    # 4. Initialize Model (GPU enabled)
    model = XGBClassifier(
        enable_categorical=True,
        tree_method="hist",
        device="cuda",
        max_depth=6,
        n_estimators=1000,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="auc",
        random_state=42
    )

    # 5. Run Cross-Validation and Log to MLflow
    print("Starting 5-Fold Cross Validation on GPU...")
    
    with mlflow.start_run(run_name="xgb_5fold_cv"):
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        # Calculate CV scores
        scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc", n_jobs=1)
        
        mean_score = scores.mean()
        std_score = scores.std()
        
        print(f"\n🔥 CV ROC-AUC Scores: {scores}")
        print(f"📈 Mean: {mean_score:.4f} (+/- {std_score:.4f})")

        # Log parameters to MLflow
        mlflow.log_param("cv_splits", 5)
        mlflow.log_param("tree_method", "hist")
        mlflow.log_param("device", "cuda")
        
        # Log aggregated metrics to MLflow
        mlflow.log_metric("roc_auc_mean", mean_score)
        mlflow.log_metric("roc_auc_std", std_score)
        
        # Log individual fold scores to MLflow
        for i, score in enumerate(scores):
            mlflow.log_metric(f"roc_auc_fold_{i+1}", score)

    print(f"\n✅ Cross-validation complete. Results logged to MLflow at {TRACKING_URI}")

if __name__ == "__main__":
    # Adjust this path if your dataset is located elsewhere
    evaluate_model_cv("/home/badr/genomic-variant-mlops/data/processed/final_training_dataset.parquet")