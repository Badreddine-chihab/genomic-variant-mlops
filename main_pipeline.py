from prefect import flow, task
import subprocess
import os
    
# On définit chaque étape comme une Task
# Le décorateur 'retries' permet de relancer si le FTP du NCBI coupe
@task(retries=2, retry_delay_seconds=30, name="Ingestion ClinVar")
def run_download_clinvar():
    print("--- Stage: Download ClinVar ---")
    subprocess.run(["python3", "src/data/download_clinvar.py"], check=True)

@task(name="Traitement ClinVar")
def run_process_clinvar():
    subprocess.run(["python3", "src/features/process_clinvar.py"], check=True)

@task(name="Nettoyage Labels")
def run_clean_labels():
    subprocess.run(["python3", "src/features/clean_labels.py"], check=True)

@task(retries=2, retry_delay_seconds=30, name="Ingestion dbSNP")
def run_download_dbsnp():
    subprocess.run(["python3", "src/data/download_dbsnp.py"], check=True)

@task(name="Traitement dbSNP")
def run_process_dbsnp():
    subprocess.run(["python3", "src/features/process_dbsnp.py"], check=True)

@task(name="Fusion Datasets")
def run_merge():
    subprocess.run(["python3", "src/features/merge_datasets.py"], check=True)

@task(name="Encodage Final")
def run_encode():
    subprocess.run(["python3", "src/features/encode_features.py"], check=True)

# Le Flow est le chef d'orchestre qui définit l'ordre
@flow(name="Genomic-Variant-MLOps-Pipeline")
def genomic_pipeline():
    # 1. Pipeline ClinVar
    run_download_clinvar()
    run_process_clinvar()
    run_clean_labels()
    
    # 2. Pipeline dbSNP
    run_download_dbsnp()
    run_process_dbsnp()
    
    # 3. Finalisation
    run_merge()
    run_encode()

if __name__ == "__main__":
    genomic_pipeline()