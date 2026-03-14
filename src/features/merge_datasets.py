import pandas as pd
import os

def merge_clinvar_dbsnp(clinvar_path, dbsnp_path, output_path):
    print(f"Chargement de la base ClinVar : {clinvar_path}")
    # On force le type String pour les clés de jointure afin d'éviter les bugs (ex: le chromosome 'X')
    df_clinvar = pd.read_csv(clinvar_path, dtype={'CHROM': str, 'POS': str, 'REF': str, 'ALT': str})
    
    print(f"Chargement des fréquences dbSNP : {dbsnp_path}")
    df_dbsnp = pd.read_csv(dbsnp_path, dtype={'CHROM': str, 'POS': str, 'REF': str, 'ALT': str})
    
    print("Exécution de la jointure (Left Join)...")
    # Fusion sur les 4 piliers qui identifient une mutation unique
    df_merged = pd.merge(df_clinvar, df_dbsnp, on=['CHROM', 'POS', 'REF', 'ALT'], how='left')
    
    # Traitement des valeurs manquantes (mutations très rares)
    df_merged['ALT_FREQ'] = df_merged['ALT_FREQ'].fillna(0.0)
    
    # Conversion propre en numérique (float)
    df_merged['ALT_FREQ'] = df_merged['ALT_FREQ'].astype(float)
    
    # Sauvegarde
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_merged.to_csv(output_path, index=False)
    
    print("-" * 50)
    print("Aperçu du dataset final prêt pour le Machine Learning :")
    print(df_merged.head())
    print("-" * 50)
    print(f"Succès ! Dataset final sauvegardé : {output_path}")
    print(f"Nombre total de variants : {len(df_merged)}")

if __name__ == "__main__":
    clinvar_csv = "data/processed/training_base.csv"
    dbsnp_csv = "data/processed/dbsnp_frequencies.csv"
    final_csv = "data/processed/final_training_dataset.csv"
    
    merge_clinvar_dbsnp(clinvar_csv, dbsnp_csv, final_csv)