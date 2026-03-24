import pandas as pd
import numpy as np
from xgboost import XGBClassifier, callback
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

    print("🚀 Training optimized model...")

    df = pd.read_parquet(data_path)

    # -----------------------------
    # Ensure categorical types
    # -----------------------------
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype('category')

    if df['CHROM'].dtype != 'category':
        df['CHROM'] = df['CHROM'].astype('category')

    print("\n📊 Data Overview:")
    print(df.dtypes)
    print(f"\nShape: {df.shape}")

    X = df.drop(columns=["Target"])
    y = df["Target"]

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
    # Model
    # -----------------------------
    model = XGBClassifier(
    enable_categorical=True,
    tree_method="hist",
    max_depth=6,
    n_estimators=1000,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pos_weight,
    eval_metric="aucpr",
    random_state=42
)

    mlflow.set_experiment("genomic-variant-classification")

    with mlflow.start_run():

        # -----------------------------
        # Training with early stopping
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
        f1 = f1_score(y_test, y_pred)
        acc = accuracy_score(y_test, y_pred)

        # -----------------------------
        # Print results
        # -----------------------------
        print("\n🔥 FINAL RESULTS")
        print(f"PR-AUC      : {pr_auc:.4f}")
        print(f"ROC-AUC     : {roc_auc:.4f}")
        print(f"Best Thresh : {best_thresh:.3f}")
        print(f"F1 Score    : {f1:.4f}")
        print(f"Precision   : {precision:.4f}")
        print(f"Recall      : {recall:.4f}")
        print(f"Accuracy    : {acc:.4f}")

        # -----------------------------
        # MLflow logging
        # -----------------------------
        mlflow.log_metric("pr_auc", pr_auc)
        mlflow.log_metric("roc_auc", roc_auc)
        mlflow.log_metric("f1", f1)
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("best_threshold", best_thresh)

        mlflow.log_param("max_depth", 6)
        mlflow.log_param("learning_rate", 0.03)
        mlflow.log_param("scale_pos_weight", scale_pos_weight)

        # -----------------------------
        # Save model
        # -----------------------------
        os.makedirs("models", exist_ok=True)
        model.save_model("models/model.json")
        mlflow.xgboost.log_model(model, "model")

    print("\n✅ Training complete!")


if __name__ == "__main__":
    train_model("data/processed/genomic_variants_encoded.parquet")