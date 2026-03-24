# Genomic Variant MLOps Project - Complete Context Prompt

## PROJECT OVERVIEW
This is an MLOps project focused on **genomic variant classification** - building and maintaining machine learning models to classify genetic variants as pathogenic, benign, or of uncertain significance (VUS). The project demonstrates production-grade MLOps practices with data versioning, pipeline orchestration, feature engineering, and model tracking.

**Key Goal:** Create a reproducible, automated pipeline for classifying genomic variants by integrating data from ClinVar (clinical significance) and dbSNP (population frequencies).

---

## TECH STACK & TOOLS
- **Language:** Python 3
- **Data Versioning:** DVC (Data Version Control)
- **Orchestration:** Prefect 3.0 (Flow/Task-based with retry logic)
- **Model Tracking:** MLflow
- **Deployment Stack:** Docker, FastAPI (planned)
- **Data Processing:** Pandas, native Python, bash tools (zcat, wget)
- **Environment:** Linux/WSL2, Python virtual environment (.venv)

---

## PROJECT STRUCTURE

```
genomic-variant-mlops/
├── data/
│   ├── raw/                          # Raw, immutable data
│   │   └── clinvar.vcf.gz           # ClinVar genetic variants (VCF format)
│   │   └── dbsnp_common.vcf.gz      # dbSNP population frequencies
│   └── processed/                    # Transformed, analysis-ready datasets
│       ├── clinvar_cleaned.csv       # 3.24M cleaned ClinVar variants
│       ├── training_base.csv         # Labels: Pathogenic vs Benign
│       ├── vus_to_predict.csv        # VUS variants for inference
│       ├── dbsnp_frequencies.csv     # Minor Allele Frequency (MAF)
│       └── final_training_dataset.csv # Merged, encoded dataset (production-ready)
│
├── src/
│   ├── data/                         # Data ingestion scripts
│   │   ├── download_clinvar.py      # Fetch ClinVar from NCBI FTP
│   │   └── download_dbsnp.py        # Fetch dbSNP frequencies
│   ├── features/                     # Feature engineering & transformation
│   │   ├── process_clinvar.py       # VCF → CSV conversion
│   │   ├── process_dbsnp.py         # Extract MAF from dbSNP
│   │   ├── clean_labels.py          # Standardize binary classification
│   │   ├── merge_datasets.py        # Left-join clinical + population data
│   │   └── encode_features.py       # Advanced feature engineering
│   ├── eda/                          # Exploratory data analysis (non-production)
│   │   ├── explore_clinvar.py
│   │   ├── explore_dbsnp.py
│   │   └── explore_data.py
│   └── models/                       # Model training & inference
│       └── train_model.py            # ML Pipeline
│
├── notebooks/
│   └── fnotebook_001.ipynb          # Sandbox for experimentation
│
├── mlruns/                           # MLflow tracking directory
│   ├── 1/ - 5/                       # Multiple experiment runs
│   └── models/                       # Model artifacts & metadata
│
├── main_pipeline.py                  # Prefect orchestration (main entry point)
├── dvc.yaml                          # DVC pipeline definition
└── Suivi_projet.md                   # Project journal (French)
```

---

## DATA PIPELINE FLOW

### Phase 1: ClinVar (Clinical Variants)
1. **Download** (`download_clinvar.py`)
   - Source: NCBI ClinVar FTP server
   - Format: VCF (Variant Call Format, compressed with bgzip)
   - Challenge Solved: Python's `gzip` module crashed after 3M lines → switched to `subprocess.Popen(['zcat'])` for robustness

2. **Process** (`process_clinvar.py`)
   - Convert VCF (text) → CSV (tabular)
   - Extract Features: `CHROM`, `POS`, `REF`, `ALT`, `Is_InDel`, `Is_Frameshift`, `CLNSIG`
   - Output: `clinvar_cleaned.csv` (3.24M rows, versionned in DVC)

3. **Clean Labels** (`clean_labels.py`)
   - Binary classification: Pathogenic (1) vs Benign (0)
   - Separate VUS (uncertain variants) into `vus_to_predict.csv`
   - Clean variants → `training_base.csv`
   - Key Stats: 1.7M VUS (~50%), 82.6% InDels are Frameshifts

### Phase 2: dbSNP (Population Frequencies)
1. **Download** (`download_dbsnp.py`)
   - Source: NCBI dbSNP common variants
   - File: `common_all_20180418.vcf.gz` (~1.5 GB)
   - Purpose: Extract population allele frequencies (MAF = Minor Allele Frequency)

2. **Process** (`process_dbsnp.py`)
   - Extract `CAF` (Common Allele Frequency) tag from INFO column
   - Output: `dbsnp_frequencies.csv` with `ALT_FREQ` feature

### Phase 3: Data Fusion (`merge_datasets.py`)
- **Join Type:** Left-join (keep all ClinVar variants)
- **Missing Values:** Ultra-rare variants not in dbSNP get `ALT_FREQ = 0.0`
- **Output:** `final_training_dataset.csv` (production-ready dataset with Target + Features)

### Phase 4: Feature Engineering (`encode_features.py`)
Advanced feature transformations:
- **Shannon Entropy (H):** Measures sequence complexity; identifies repetitive regions prone to polymerase errors
  - Formula: $H(S) = -\sum_{i \in \{A, C, G, T\}} P(i) \log_2 P(i)$
- **Non-Linear Impact Score:** Interaction between mutation magnitude (length) and rarity
- Additional biocheminformatic features for improved classification

---

## ORCHESTRATION APPROACH

### Prefect 3.0 Pipeline (`main_pipeline.py`)
**Why Prefect?** Transforms ad-hoc scripts → production-grade, monitored workflows.

**Architecture:**
- **Tasks:** Individual operations wrapped in retry logic
  - Retries=2, Delay=30s for network failures (NCBI FTP instability)
- **Flow:** Orchestrates task execution order and dependencies
- **Monitoring:** Local Prefect dashboard logs, tracks data lineage, handles failures

**Execution Order:**
```
download_clinvar → process_clinvar → clean_labels
                                    ↓
                download_dbsnp → process_dbsnp
                                    ↓
                            merge_datasets
                                    ↓
                            encode_features
                                    ↓
                            train_model
```

### DVC Pipeline (`dvc.yaml`)
Defines dependencies & outputs for reproducibility:
- Each stage (download, process, merge) is tracked
- Ensures re-runs only occur when inputs change
- Works with Prefect for end-to-end reproducibility

---

## MODEL TRAINING & TRACKING

**Location:** `src/models/train_model.py`

**MLflow Integration:**
- Tracks experiments in `mlruns/` directory
- Models stored in `mlruns/{experiment_id}/models/`
- Artifacts: Model files (.ubj), conda.yaml, requirements.txt, python_env.yaml

**Current Status:**
- 5+ experiment runs tracked
- Multiple model iterations with different hyperparameters
- Reproducible environment configs in each run

---

## KEY TECHNICAL CHALLENGES SOLVED

1. **Large File Processing:** VCF files too large for Python's `gzip` → used `zcat` subprocess for streaming
2. **Network Instability:** NCBI FTP timeouts → added Prefect task retries with exponential backoff
3. **Feature Extraction:** Binary classification from multi-category labels → standardized encoding with isolated VUS set
4. **Data Quality:** Missing values in population frequencies → handled with default (0.0) for ultra-rare variants

---

## CURRENT STATE & NEXT STEPS

**Completed:**
- Data ingestion pipelines (ClinVar, dbSNP)
- Feature engineering & dataset preparation
- Prefect orchestration framework
- MLflow experiment tracking
- Advanced feature metrics (entropy, impact scores)

**In Progress / Upcoming:**
- Model training optimization
- Hyperparameter tuning
- FastAPI deployment service
- Docker containerization for reproducibility
- Production inference pipeline for VUS classification

---

## HOW TO CONTRIBUTE / USE THIS PROMPT

When asking for help with this project, reference:
- **Pipeline Modifications:** See `main_pipeline.py` and `dvc.yaml`
- **Feature Engineering:** See `src/features/encode_features.py`
- **Data Processing Issues:** Check `src/data/` and `src/features/`
- **Model Tracking:** Check `mlruns/` structure and `src/models/train_model.py`

This project demonstrates **end-to-end MLOps**: from raw genomic data → reproducible pipelines → tracked experiments → production-ready inference.
