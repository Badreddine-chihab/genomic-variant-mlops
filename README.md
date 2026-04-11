# 🧬 Genomic Variant Classification - MLOps

XGBoost GPU-accelerated classification (pathogenic vs benign) with MLflow tracking.

**Model**: PR-AUC 0.8234 | ROC-AUC 0.8756 | CV 0.8732 ± 0.0054

---

## 📚 Docs

- **[GUIDE.md](GUIDE.md)** - Setup & workflows ⭐ START HERE
- **[ROADMAP.md](ROADMAP.md)** - Progress & phases
- **[AWS_DVC_SETUP.md](AWS_DVC_SETUP.md)** - Data versioning
- **[MLFLOW_REGISTRY_SETUP.md](MLFLOW_REGISTRY_SETUP.md)** - Model registry

---

## 📁 Structure

```
src/data/         Extract & clean dbNSFP files
src/features/     Feature engineering & optimization
src/model/        Training, evaluation, registry
data/processed/   Final datasets
notebooks/        Analysis
mlruns/           MLflow experiments
```

---

## ⚡ 5-Min Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full pipeline
python src/data/Stitching_chr.py
python src/features/encode_features.py
python src/features/optimization.py
python src/model/train_model.py
python src/model/eval.py
python src/model/register_model.py

# View results
mlflow ui
```

See [GUIDE.md](GUIDE.md) for details.

---

## ✅ Status

- **Phases 1-4**: ✅ Complete
- **Phase 5**: 🔄 REST API + CI/CD (in progress)
- **Phase 6**: 📋 Monitoring + A/B testing

See [ROADMAP.md](ROADMAP.md).
