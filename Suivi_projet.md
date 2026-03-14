# Journal de Bord du Projet : MLOps en Santé
**Projet :** Optimisation du cycle de vie des modèles de Machine Learning pour une création de valeur organisationnelle durable (Analyse de variants génomiques).
**Auteur :** Badreddine Chihab

---

## 1. Conception de l'Architecture MLOps
Avant d'écrire la moindre ligne de code, l'architecture globale du pipeline a été définie pour répondre aux exigences de reproductibilité et d'automatisation d'un environnement de production.
* **Approche :** 100% Open Source en environnement Linux (WSL2).
* **Stack Technique :**
    * *Data Versioning :* DVC
    * *Orchestration :* Prefect / DVC Pipelines
    * *Traitement :* Python natif (subprocess, Pandas) et outils bash (`zcat`, `wget`)
    * *Tracking :* MLflow
    * *Déploiement :* Docker & FastAPI

## 2. Initialisation de l'Infrastructure et du Dépôt
Création de l'environnement de base pour assurer l'isolation et le versioning hybride (Code + Données).
* Création du dépôt Git `genomic-variant-mlops`.
* Mise en place de l'environnement virtuel Python (`.venv`).
* Initialisation de DVC (`dvc init`) pour gérer les fichiers lourds (bases de données génomiques).
* Création de l'arborescence standard MLOps :
    * `data/raw/` : Données brutes intouchables.
    * `data/processed/` : Données transformées.
    * `notebooks/` : Espace d'exploration (Sandbox).
    * `src/` : Scripts d'automatisation en production.

## 3. Phase 1 : Ingestion et Prétraitement de ClinVar

### 3.1. Téléchargement des données brutes
* **Script :** `src/data/download_clinvar.py`
* **Action :** Récupération du fichier VCF complet de ClinVar (GRCh38) depuis le serveur FTP du NCBI.
* **Défi technique résolu :** Le téléchargement initial via `urllib` a généré un fichier corrompu (erreur `zlib.error`). Remplacement par un appel système `wget -c` pour garantir un téléchargement robuste et reprenable.
* **Versioning :** Suivi du fichier `clinvar.vcf.gz` avec DVC.

### 3.2. Extraction des Features (Feature Engineering)
* **Script :** `src/features/process_clinvar.py`
* **Action :** Transformation du fichier texte compressé `.vcf.gz` en format tabulaire `.csv`.
* **Features extraites :** `CHROM`, `POS`, `REF`, `ALT`, `Is_InDel` (booléen), `Is_Frameshift` (booléen calculé via le modulo 3 de la différence de longueur), `CLNSIG` (Signification clinique).
* **Défi technique résolu :** Le module standard `gzip` de Python a crashé après 3 millions de lignes à cause de la compression par blocs (`bgzip`). Contournement du problème en déléguant la décompression au système d'exploitation via `subprocess.Popen(['zcat', ...])`.
* **Résultat :** Génération de `clinvar_cleaned.csv` (~3.24 millions de variants), versionné avec DVC.

### 3.3. Analyse Exploratoire (EDA) et Nettoyage des Labels
* **Script d'exploration :** `src/eda/explore_data.py`
* **Constat :** Plus de la moitié des variants (1.7M) sont des VUS (Variants of Uncertain Significance). Les autres classes sont fragmentées. 82.6% des InDels génèrent un Frameshift.
* **Script de nettoyage :** `src/features/clean_labels.py`
* **Action :** Standardisation du dataset pour l'apprentissage supervisé (Classification binaire).
    * Classe 1 (Pathogène) : Regroupement de `Pathogenic`, `Likely_pathogenic`, etc.
    * Classe 0 (Bénin) : Regroupement de `Benign`, `Likely_benign`, etc.
    * Séparation stricte : Les VUS sont isolés dans `vus_to_predict.csv` pour l'inférence future. Les variants clairs sont stockés dans `training_base.csv`.

## 4. Refactoring de l'Architecture Logicielle
Pour préparer l'orchestration automatisée, le dossier `src/` a été réorganisé selon les standards de l'industrie :
* `src/data/` : Scripts de téléchargement (ingestion).
* `src/features/` : Scripts de transformation et de nettoyage.
* `src/eda/` : Scripts d'exploration (isolés du pipeline de production).
* `src/models/` : Préparé pour les algorithmes de Machine Learning.
* Ajout des fichiers `__init__.py` pour la modularité.

## 5. Phase 2 : Ingestion de dbSNP (En cours)

### 5.1. Téléchargement des fréquences alléliques
* **Script :** `src/data/download_dbsnp.py`
* **Action :** Téléchargement du fichier des variants communs (`common_all_20180418.vcf.gz`, ~1.5 Go) pour extraire la fréquence allélique mineure (MAF), une feature critique pour la classification.
* **Versioning :** Fichier lourd ajouté à DVC.

### 5.2. Exploration initiale
* **Script :** `src/eda/explore_dbsnp.py`
* **Action :** Lecture via `zcat` des premières lignes du VCF de dbSNP pour identifier la structure de la colonne INFO et repérer les balises de fréquences (`CAF=` ou `FREQ=`).

### 5.3. Extraction des Fréquences Alléliques (MAF)
* **Script :** `src/features/process_dbsnp.py`
* **Action :** Parcours du fichier compressé via `zcat` pour isoler la balise `CAF=` (Common Allele Frequency) dans la colonne INFO.
* **Feature extraite :** `ALT_FREQ` (Fréquence de la mutation dans la population).
* **Résultat :** Génération du fichier `dbsnp_frequencies.csv` (versionné avec DVC).

## 6. Phase 3 : Fusion et Finalisation du Dataset (Data Merging)
* **Script :** `src/features/merge_datasets.py`
* **Action :** Réalisation d'une jointure gauche (Left Join) avec Pandas pour combiner la base clinique (ClinVar) et les statistiques mondiales (dbSNP).
* **Traitement des valeurs manquantes :** Les mutations absentes de dbSNP (ultra-rares) se voient attribuer une fréquence `ALT_FREQ = 0.0`.
* **Résultat :** Création du `final_training_dataset.csv`, le tableau de bord définitif prêt pour l'entraînement algorithmique (Target + Features), versionné avec DVC.

## 7. Phase 4 : Modernisation de l'Orchestration (Migration Prefect)
Pour transformer un projet de recherche en un pipeline de production robuste, l'automatisation doit être supervisée et résiliente.
* **Outil :** Prefect 3.0.
* **Script central :** `main_pipeline.py`.
* **Action :** Migration des scripts individuels vers un système de flux orchestré (Flows & Tasks).
* **Défi technique résolu :** Mise en place de décorateurs `@task(retries=2, retry_delay_seconds=30)` pour gérer les instabilités réseaux lors des requêtes FTP vers le NCBI, évitant ainsi l'échec total du pipeline en cas de micro-coupure.
* **Résultat :** Déploiement d'un Dashboard local (via `prefect server start`) permettant le monitoring en temps réel, la gestion des logs centralisée et une observabilité complète du cycle de vie des données.

## 8. Phase 5 : Ingénierie de Caractéristiques Avancée (Feature Engineering)
Afin d'extraire une valeur maximale des données génomiques, le script d'encodage a été enrichi par des concepts de théorie de l'information et de biochimie moléculaire.
* **Script :** `src/features/encode_features.py`.

### 8.1. Entropie de Shannon ($H$)
* **Action :** Calcul de la complexité locale des séquences REF et ALT pour identifier les zones répétitives (faible entropie) souvent sujettes à des erreurs de polymérase.
* **Formule :** $H(S) = -\sum_{i \in \{A, C, G, T\}} P(i) \log_2 P(i)$

### 8.2. Score d'Impact Non-Linéaire ($S_{impact}$)
* **Action :** Création d'une feature d'interaction pondérant la magnitude de la mutation (longueur) par sa rareté statistique.
* **Justification :** Plus une mutation est longue, casse le cadre de lecture (Frameshift) et possède une fréquence faible dans la population (`ALT_FREQ`), plus son potentiel pathogène est mathématiquement élevé.
* **Formule :** $S_{impact} = \frac{\text{Is\_Frameshift} \times |\Delta_{Length}|}{\text{ALT\_FREQ} + \epsilon}$

### 8.3. Normalisation et Réduction de l'Asymétrie
* **Action :** Application de `np.log1p` sur la fréquence allélique.
* **Objectif :** Réduire le **skewness** (asymétrie) massif de la distribution des fréquences (concentrées vers 0) pour faciliter la convergence des algorithmes d'apprentissage.

## 9. Phase 6 : Optimisation Statistique et Encodage (Selective Scaling)
Une réflexion sur la sémantique des données a conduit à une stratégie de mise à l'échelle hybride pour garantir la performance du modèle.
* **Script :** `src/features/encode_features.py`.

### 9.1. Standardisation Sélective (Selective Scaler)
* **Action :** Application du `StandardScaler` ($Z$-score) uniquement sur les variables **continues** (`ALT_FREQ`, `Impact_Score`, `Entropy`, `Delta_Length`).
* **Défi technique résolu :** Exclusion stricte des variables **binaires** (Flags 0/1) et des colonnes issues du **One-Hot Encoding** de la standardisation.
* **Justification :** Préserver la sémantique biologique "Oui/Non" du signal et éviter de distordre l'information de rareté par un décentrage mathématique inutile.

### 9.2. Réduction de Dimensionnalité et Optimisation RAM
* **Action :** Suppression définitive des colonnes `CHROM` et `POS`.
* **Justification MLOps :** 1. **Généralisation :** Prévention du sur-apprentissage (**overfitting**) sur des coordonnées géomiques spécifiques (le modèle doit apprendre la biologie de la mutation, pas son adresse).
    2. **Stabilité :** Optimisation drastique de la consommation de mémoire vive sous WSL2, résolvant les problèmes de déconnexion de l'IDE (VS Code) lors du traitement de 3,2 millions de lignes.

## 10. Prochaines Étapes : Modélisation et Tracking MLflow
Le dataset étant désormais qualifié de **Gold Standard** (propre, encodé et optimisé), le projet entre dans sa phase d'apprentissage supervisé.
* **Modélisation :** Implémentation de l'algorithme **XGBoost** pour sa gestion native des données tabulaires mixtes.
* **Expérimentation :** Utilisation de **MLflow** pour le versioning des modèles et le tracking des métriques de performance (Accuracy, Precision, Recall, F1-Score).