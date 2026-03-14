import pandas as pd

def analyze_clinvar(csv_path):
    print(f"Chargement des données depuis {csv_path}...\n")
    df = pd.read_csv(csv_path)
    
    print("-" * 40)
    print(f"Nombre total de variants : {len(df)}")
    print("-" * 40)
    
    print("\nDistribution des 10 labels cliniques (CLNSIG) les plus fréquents :")
    print(df['CLNSIG'].value_counts().head(10))
    
    print("\nRépartition InDel vs SNP (en %) :")
    # 0 = SNP, 1 = InDel
    print(df['Is_InDel'].value_counts(normalize=True) * 100)
    
    print("\nImpact des Frameshifts parmi les InDels (en %) :")
    indels_only = df[df['Is_InDel'] == 1]
    print(indels_only['Is_Frameshift'].value_counts(normalize=True) * 100)

if __name__ == "__main__":
    csv_file = "data/processed/clinvar_cleaned.csv"
    analyze_clinvar(csv_file)