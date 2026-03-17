from matplotlib.pyplot import hist
import pandas as pd
import numpy as np
import xgboost as xgb
import mlflow
import mlflow.xgboost
import optuna
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, accuracy_score, average_precision_score,
    fbeta_score, matthews_corrcoef, roc_auc_score, confusion_matrix
)
import os

# --- CONFIGURATION ---
INPUT_DATA = "data/processed/encoded_training_dataset.csv"
EXPERIMENT_NAME = "Genomic_Variant_Advanced_Metrics"
N_TRIALS = 15 

def train_best_model():
    print(f"📂 Chargement des données : {INPUT_DATA}")
    df = pd.read_csv(INPUT_DATA)
    X = df.drop(columns=['Target'])
    y = df['Target']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    ratio = len(y_train[y_train == 0]) / len(y_train[y_train == 1])
    print(f"⚖️ Ratio d'imbalance : {ratio:.2f}")

    def objective(trial):
        params = {
            "objective": "binary:logistic",
            "n_estimators": 331, #332
            "max_depth": 10, #10
            "learning_rate": 0.09,#0.09
            "subsample": 0.890, #0,890
            "colsample_bytree": 0.737,#0.737
            "scale_pos_weight": ratio,
            "eval_metric": "aucpr",
            "use_label_encoder": False,
            "enable_categorical": True,
            "tree_method": "hist"
        }

        with mlflow.start_run(nested=True):
            model = xgb.XGBClassifier(**params)
            model.fit(X_train, y_train)
            
            y_proba = model.predict_proba(X_test)[:, 1]
            # On utilise le PR_AUC pour guider Optuna (meilleur pour l'imbalance)
            score = average_precision_score(y_test, y_proba)
            
            mlflow.log_params(params)
            mlflow.log_metric("trial_PR_AUC", score)
            return score

    mlflow.set_experiment(EXPERIMENT_NAME)
    
    with mlflow.start_run(run_name="Final_Model_With_Full_Metrics"):
        print("🚀 Lancement de l'optimisation...")
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=N_TRIALS)

        # Entraînement du meilleur modèle
        best_model = xgb.XGBClassifier(**study.best_params, scale_pos_weight=ratio)
        best_model.fit(X_train, y_train)

        # Prédictions et Probabilités
        y_proba = best_model.predict_proba(X_test)[:, 1]
        threshold = 0.4 
        y_pred = (y_proba >= threshold).astype(int)

        # --- CALCUL DES MÉTRIQUES AVANCÉES ---
        report = classification_report(y_test, y_pred, output_dict=True)
        acc = accuracy_score(y_test, y_pred)
        pr_auc = average_precision_score(y_test, y_proba)
        roc_auc = roc_auc_score(y_test, y_proba)
        
        # F2-Score : Donne 2x plus de poids au Recall qu'à la Precision
        f2 = fbeta_score(y_test, y_pred, beta=2)
        
        # MCC : Le coefficient de corrélation de Matthews (le plus robuste pour l'imbalance)
        mcc = matthews_corrcoef(y_test, y_pred)
        
        # Matrice de Confusion
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

        # --- LOGGING MLFLOW ---
        mlflow.log_params(study.best_params)
        mlflow.log_metric("final_accuracy", acc)
        mlflow.log_metric("final_PR_AUC", pr_auc)
        mlflow.log_metric("final_ROC_AUC", roc_auc)
        mlflow.log_metric("final_Recall_C1", report['1']['recall'])
        mlflow.log_metric("final_Precision_C1", report['1']['precision'])
        mlflow.log_metric("final_F2_Score", f2)
        mlflow.log_metric("final_MCC", mcc)
        
        # Log des erreurs brutes (très utile pour l'analyse)
        mlflow.log_metric("True_Positives", tp)
        mlflow.log_metric("False_Negatives", fn) # Ce qu'on veut minimiser absolument

        mlflow.xgboost.log_model(best_model, "best_genomic_model")

        print("\n--- 🚀 Rapport Final ---")
        print(f"F2-Score (Recall Prioritized): {f2:.4f}")
        print(f"MCC (Robustness): {mcc:.4f}")
        print(f"PR-AUC: {pr_auc:.4f}")
        print(f"FN (Variants ratés): {fn}")

if __name__ == "__main__":
    if not os.path.exists("mlruns"): os.makedirs("mlruns")
    train_best_model()