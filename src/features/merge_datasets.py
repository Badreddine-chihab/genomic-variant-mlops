import pandas as pd
import os

def merge_clinvar_dbsnp(clinvar_path, dbsnp_path, output_path):
    print(f"Chargement ClinVar : {clinvar_path}")
    df_clinvar = pd.read_csv(
        clinvar_path,
        dtype={'CHROM': str, 'POS': str, 'REF': str, 'ALT': str}
    )

    print(f"Chargement dbSNP : {dbsnp_path}")
    df_dbsnp = pd.read_csv(
        dbsnp_path,
        dtype={'CHROM': str, 'POS': str, 'REF': str, 'ALT': str}
    )

    print("Fusion (Left Join)...")
    df_merged = pd.merge(
        df_clinvar,
        df_dbsnp,
        on=['CHROM', 'POS', 'REF', 'ALT'],
        how='left'
    )

    # -----------------------------
    # Handle missing frequencies
    # -----------------------------
    df_merged['ALT_FREQ'] = df_merged['ALT_FREQ'].fillna(0.0)

    # Convert to float
    df_merged['ALT_FREQ'] = df_merged['ALT_FREQ'].astype(float)

    # -----------------------------
    # VALIDATION (CRITICAL)
    # -----------------------------
    assert (df_merged['ALT_FREQ'] >= 0).all(), "❌ Negative frequencies detected!"
    assert (df_merged['ALT_FREQ'] <= 1).all(), "❌ Frequencies > 1 detected!"

    # -----------------------------
    # Remove duplicates
    # -----------------------------
    df_merged = df_merged.drop_duplicates(
        subset=['CHROM','POS','REF','ALT']
    )

    # -----------------------------
    # Convert POS back to int
    # -----------------------------
    df_merged['POS'] = df_merged['POS'].astype(int)

    # -----------------------------
    # Merge stats (VERY USEFUL)
    # -----------------------------
    matched = df_merged['ALT_FREQ'].gt(0).sum()
    total = len(df_merged)

    print(f"Variants avec fréquence dbSNP: {matched}")
    print(f"Variants rares (non trouvés): {total - matched}")

    print("Statistiques ALT_FREQ:")
    print(df_merged['ALT_FREQ'].describe())

    # -----------------------------
    # Save
    # -----------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_merged.to_csv(output_path, index=False)

    print("-" * 50)
    print("Aperçu dataset final :")
    print(df_merged.head())
    print("-" * 50)
    print(f"✅ Dataset sauvegardé : {output_path}")
    print(f"Total variants : {len(df_merged)}")


if __name__ == "__main__":
    merge_clinvar_dbsnp(
        clinvar_path="data/processed/training_base.csv",
        dbsnp_path="data/processed/dbsnp_frequencies.csv",
        output_path="data/processed/final_training_dataset.csv"
    )