import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score
)
import mlflow
import mlflow.xgboost
import os

def find_best_threshold(y_true, y_probs):
    thresholds = np.linspace(0.05, 0.95, 50)
    best_f1 = 0
    best_thresh = 0.5

    for t in thresholds:
        y_pred = (y_probs >= t).astype(int)
        f1 = f1_score(y_true, y_pred)

        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t

    return best_thresh, best_f1

def train_model(data_path):
    print("🚀 Training optimized model with RTX 4070 GPU...")

    # Ensure the script runs from its own directory to resolve relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print(f"Loading data from: {data_path}")
    df = pd.read_parquet(data_path)

    # -----------------------------
    # Ensure categorical types for XGBoost
    # -----------------------------
    cat_cols = ["CHROM", "REF_Base", "ALT_Base", "mutation_type"]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    print("\n📊 Data Overview:")
    print(df.dtypes)
    print(f"\nShape: {df.shape}")

    # -----------------------------
    # Smart Target Column Detection
    # -----------------------------
    target_col = "Target" if "Target" in df.columns else "target"
    
    if target_col not in df.columns:
        raise KeyError(f"Target column missing! Available columns: {df.columns.tolist()}")

    X = df.drop(columns=[target_col])
    y = df[target_col]

    # -----------------------------
    # Split data
    # -----------------------------
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )

    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42
    )

    print(f"\n📦 Train size: {len(X_train)}")
    print(f"📦 Val size: {len(X_val)}")
    print(f"📦 Test size: {len(X_test)}")

    # -----------------------------
    # Class imbalance
    # -----------------------------
    scale_pos_weight = (len(y_train) - sum(y_train)) / sum(y_train)
    print(f"\n⚖️ scale_pos_weight: {scale_pos_weight:.2f}")

    # -----------------------------
    # Model Setup (GPU Enabled)
    # -----------------------------
    model = XGBClassifier(
        enable_categorical=True,
        tree_method="hist",
        device="cuda",  # Triggers the RTX 4070
        max_depth=6,
        n_estimators=1000,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        early_stopping_rounds=50, # Stops training if validation stops improving
        random_state=42
    )

    mlflow.set_tracking_uri("file:///home/badr/genomic-variant-mlops/mlruns")
    mlflow.set_experiment("genomic-variant-classification")

    with mlflow.start_run():
        print("\n⚙️ Starting training on GPU...")

        # -----------------------------
        # Training
        # -----------------------------
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=100
        )

        # -----------------------------
        # Predictions
        # -----------------------------
        y_probs = model.predict_proba(X_test)[:, 1]

        # -----------------------------
        # Metrics
        # -----------------------------
        pr_auc = average_precision_score(y_test, y_probs)
        roc_auc = roc_auc_score(y_test, y_probs)

        # Optimize threshold
        best_thresh, best_f1 = find_best_threshold(y_test, y_probs)
        y_pred = (y_probs >= best_thresh).astype(int)

        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        acc = accuracy_score(y_test, y_pred)

        # -----------------------------
        # Print results
        # -----------------------------
        print("\n🔥 FINAL RESULTS")
        print(f"PR-AUC      : {pr_auc:.4f}")
        print(f"ROC-AUC     : {roc_auc:.4f}")
        print(f"Best Thresh : {best_thresh:.3f}")
        print(f"F1 Score    : {best_f1:.4f}")
        print(f"Precision   : {precision:.4f}")
        print(f"Recall      : {recall:.4f}")
        print(f"Accuracy    : {acc:.4f}")

        # -----------------------------
        # MLflow logging
        # -----------------------------
        mlflow.log_metric("pr_auc", pr_auc)
        mlflow.log_metric("roc_auc", roc_auc)
        mlflow.log_metric("f1", best_f1)
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("best_threshold", best_thresh)

        mlflow.log_param("tree_method", "hist")
        mlflow.log_param("device", "cuda")
        mlflow.log_param("max_depth", 6)
        mlflow.log_param("learning_rate", 0.03)
        mlflow.log_param("scale_pos_weight", scale_pos_weight)

        # -----------------------------
        # Save model
        # -----------------------------
        os.makedirs("../model", exist_ok=True)
        model.save_model("../model/xgboost_gpu_model.json")
        mlflow.xgboost.log_model(model, "model")

    print("\n✅ Training complete! Model saved and logged to MLflow.")

if __name__ == "__main__":
    train_model("/home/badr/genomic-variant-mlops/data/processed/optimized_training_dataset.parquet")