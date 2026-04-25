# 🧬 Genomic Variant Classification - MLOps Pipeline

This project implements an industrial-grade MLOps pipeline to classify genomic variants (Pathogenic vs Benign). It leverages GPU acceleration for XGBoost, automated orchestration with Prefect 3.0, and full experiment tracking with MLflow.

## 📊 Model Performance
Results obtained on the **RTX 4070 GPU** with a dataset of **350k+ variants**:
- **PR-AUC**: `0.9652` (Primary metric for imbalanced genomic data)
- **ROC-AUC**: `0.9311`
- **F1-Score**: `0.8862`
- **5-Fold Cross-Validation**: `0.9644 ± 0.0002` (Extremely high stability)
- **Best Classification Threshold**: `0.3255`

---

## 🏗️ Technical Stack
- **Orchestration**: [Prefect 3.0](https://www.prefect.io/) (Task management & caching)
- **Tracking & Registry**: [MLflow](https://mlflow.org/) (Experiment metadata & model versioning)
- **Data Engineering**: [Polars](https://pola.rs/) (High-performance Lazy API for large genomic files)
- **Data Versioning**: [DVC](https://dvc.org/) + **AWS S3** (Remote storage)
- **Model**: **XGBoost** (GPU-accelerated `hist` tree method)
- **Explainability**: **SHAP** (Biological feature importance: SIFT, CADD, PolyPhen-2)

---

## 📁 Project Structure
```text
.
├── config/             # YAML configs (paths, training, aws, validation)
├── data/               # RAW (DVC-tracked) and Processed datasets
├── notebooks/          # Exploratory Data Analysis
├── reports/figures/    # SHAP summary and importance plots
├── src/
│   ├── data/           # Chromosome stitching (Streaming)
│   ├── features/       # Feature encoding & engineering
│   ├── model/          # Training, Eval (CV), SHAP, Model Manager
│   └── orchestration/  # Config utilities & AWS S3 logic
├── run_pipeline.py     # Main Entry Point (Prefect Flow)
└── requirements.txt    # Project dependencies
⚡ Quick Start
1. Environment Setup
Bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
2. Launch Orchestration Server
In a separate terminal:

Bash
prefect server start
# View dashboard at [http://127.0.0.1:4200](http://127.0.0.1:4200)
3. Execute Pipeline
Bash
python run_pipeline.py
Note: The pipeline automatically skips tasks if output files already exist (Smart Caching).

🏛️ Model Governance (manager.py)
The pipeline includes an automated governance gate:

Validate: Checks if the new model meets the PR-AUC > 0.95 threshold.

Register: Versions the model in the MLflow Model Registry.

Promote: Assigns the @Production alias to the best performing model.

✅ Project Status
[x] Phase 1-4: Automated Data Engineering & GPU Training.

[x] Phase 5: Prefect Orchestration & SHAP Explainability.

[ ] Phase 6: REST API Deployment (FastAPI).

[ ] Phase 7: GitHub Actions CI/CD Integration.


---
