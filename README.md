# Prédiction de la Pathogénicité des Variants Génomiques – Pipeline MLOps End-to-End

Optimisation du cycle de vie des modèles de Machine Learning pour la prédiction de pathogénicité des variants génomiques, basé sur la base de données dbNSFP. Ce projet met en œuvre les meilleures pratiques MLOps pour garantir la reproductibilité, la traçabilité et la robustesse du pipeline, de la gestion des données à l’inférence en temps réel.

---

## Architecture du Pipeline

- **Stockage & Versionnage des Données**
	- Données brutes stockées sur AWS S3 (~30 Go)
	- Versionnage local et distant via DVC (Data Version Control) avec hardlinks pour optimiser l’espace disque

- **Orchestration**
	- Orchestrateur Prefect assurant l’idempotence et l’exécution conditionnelle des étapes (pull DVC, Feature Engineering, entraînement, gouvernance)

- **Modélisation**
	- Entraînement d’un modèle XGBoost (XGBClassifier) optimisé GPU (NVIDIA RTX 4070)

- **Tracking & Registry**
	- MLflow avec backend SQLite (mlflow.db) pour le suivi des expériences et le Model Registry
	- Script de gouvernance promouvant automatiquement le meilleur modèle (F1-Score) en "Production"

- **Service & Déploiement**
	- API FastAPI chargeant dynamiquement le modèle "Production" depuis MLflow
	- Endpoint `/predict` pour l’inférence en temps réel (payload JSON)

---

## Prérequis

- **Système** : WSL Ubuntu (ou Linux équivalent)
- **Python** : 3.8+
- **GPU** : NVIDIA RTX 4070 (ou compatible CUDA)
- **Pilotes** : CUDA Toolkit & cuDNN installés
- **Outils** :
	- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
	- [DVC](https://dvc.org/doc/install)
	- [Prefect](https://docs.prefect.io/)
	- [MLflow](https://mlflow.org/)
	- [Uvicorn](https://www.uvicorn.org/)
	- [Git](https://git-scm.com/)

---

## Installation

```bash
# 1. Cloner le dépôt

cd genomic-variant-mlops

# 2. Créer et activer l’environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances Python
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurer AWS CLI (accès S3 requis)
aws configure

# 5. Synchroniser les données (DVC)
dvc pull -f
```

---

## Exécution du Pipeline

Lancer l’orchestrateur Prefect pour exécuter l’ensemble du pipeline (data, feature engineering, entraînement, validation, gouvernance) :

```bash
python run_pipeline.py
```

---

## Interface de Suivi des Expériences

Lancer MLflow UI pour visualiser les expériences et le Model Registry (backend SQLite) :

```bash
mlflow ui --backend-store-uri sqlite:///$(pwd)/mlflow.db --default-artifact-root $(pwd)/mlruns
```

Accès via [http://localhost:5000](http://localhost:5000)

---

## Lancement de l’API d’Inférence

Démarrer le serveur FastAPI avec Uvicorn :

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

- Documentation interactive Swagger : [http://localhost:8000/docs](http://localhost:8000/docs)

### Exemple de Requête JSON pour `/predict`

```json
{
  "CHROM": "11",
  "SIFT": 0.1550000011920929,
  "PolyPhen": 0,
  "CADD": 1.406000018119812,
  "ALT_FREQ": 0,
  "Is_InDel": 0,
  "Delta_Length": 0,
  "indel_size": 0,
  "Is_Frameshift": 0,
  "REF_Base": "C",
  "ALT_Base": "T",
  "mutation_type": "C_T",
  "freq_log": 0,
  "rare_variant": 1,
  "is_ultra_rare": 1,
  "is_large_indel": 0,
  "CADD_high": 0,
  "CADD_very_high": 0,
  "SIFT_damaging": 0,
  "PolyPhen_damaging": 0,
  "CADD_x_rare": 1.406000018119812,
  "Impact_Score": 2,
  "rare_impact": 2,
  "normalized_pos": 0.0014295419678092003,
  "pos_bin": 0,
  "pos_freq_interaction": 0,
  "is_transition": 1,
  "is_transversion": 0,
  "chrom_freq_mean": 0.007077359594404697,
  "chrom_rare_rate": 0.9596304893493652
}
```

---

## Notes complémentaires

- Le pipeline est idempotent : chaque étape vérifie la présence des artefacts avant exécution.
- La gouvernance automatise la promotion du meilleur modèle en production.
- L’API charge dynamiquement le modèle "Production" depuis MLflow pour garantir la cohérence des prédictions.

---

**Contact** : [Votre Nom] – [Votre Email]  
**Encadrant** : [Nom de l’encadrant]  
**Année** : 2026

---
