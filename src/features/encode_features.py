import pandas as pd
import numpy as np
import os

# Longueurs des chromosomes (GRCh38) - Crucial pour la position normalisée
CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415
}

def encode_genetic_features(input_path, output_path):
    print("🧬 Lancement du Smart Encoding (Version Ingénieur)...")

    # 1. Chargement et Nettoyage de base
    df = pd.read_csv(input_path)
    
    # On supprime tout de suite les colonnes inutiles pour libérer la RAM
    to_drop = ["population_frequency", "very_rare_variant", "is_C_to_T", 
               "is_G_to_A", "is_CpG_mutation", "freq_log"]
    df.drop(columns=to_drop, errors="ignore", inplace=True)

    # 2. Conversion des types pour économiser 70% de RAM
    df["Target"] = df["Target"].astype("int8")
    df["Is_InDel"] = df["Is_InDel"].astype("int8")
    df["Is_Frameshift"] = df["Is_Frameshift"].astype("int8")
    df["ALT_FREQ"] = df["ALT_FREQ"].astype("float32").fillna(0)

    # 3. Logique de Longueur (Delta_Length)
    # Très important pour les INDELs (ex: AGCT -> ACT = -1)
    df["Delta_Length"] = (df["ALT"].str.len() - df["REF"].str.len()).astype("int16")

    # 4. LOGIQUE SMART INDEL (Anchor + Placeholder)
    # On évite le piège "A devient A" pour les insertions/délétions
    ref_anchor = df["REF"].str[0].str.upper()
    alt_anchor = df["ALT"].str[0].str.upper()

    # Si c'est un INDEL, on utilise le tiret "-"
    df["REF_Base"] = ref_anchor
    df["ALT_Base"] = np.where(df["Is_InDel"] == 0, alt_anchor, "-")

    # Création du type de mutation (Substitution vs INDEL)
    df["mutation_type"] = np.where(
        df["Is_InDel"] == 0,
        ref_anchor + "_" + alt_anchor,
        "INDEL"
    )

    # 5. Features d'Interactions (Boost de performance)
    df["rare_variant"] = (df["ALT_FREQ"] < 0.01).astype("int8")
    df["Impact_Score"] = (df["Is_Frameshift"] * df["Delta_Length"].abs()).astype("float32")
    
    # Cette colonne aide l'IA à se focus sur les mutations rares et graves
    df["rare_impact"] = (df["rare_variant"] * df["Impact_Score"]).astype("float32")

    # 6. Positionnement Génomique
    df["CHR_Length"] = df["CHROM"].astype(str).map(CHR_LENGTHS)
    df = df.dropna(subset=["CHR_Length"]) # On enlève les chromosomes inconnus
    
    df["normalized_pos"] = (df["POS"] / df["CHR_Length"]).astype("float32")
    df["pos_bin"] = pd.qcut(df["POS"], q=10, labels=False, duplicates="drop").astype("int8")

    # 7. Transition / Transversion (Uniquement pour les substitutions)
    transition_pairs = {"A_G","G_A","C_T","T_C"}
    mut_pair = ref_anchor + "_" + alt_anchor
    df["is_transition"] = (mut_pair.isin(transition_pairs) & (df["Is_InDel"] == 0)).astype("int8")
    df["is_transversion"] = ((~mut_pair.isin(transition_pairs)) & (df["Is_InDel"] == 0)).astype("int8")

    # 8. Passage au format CATÉGORIEL NATIF (Le secret anti-crash)
    # On ne fait PLUS de One-Hot (get_dummies), on laisse XGBoost gérer
    cat_cols = ["CHROM", "REF_Base", "ALT_Base", "mutation_type"]
    for col in cat_cols:
        df[col] = df[col].astype("category")

    # 9. Nettoyage final des colonnes brutes (Texte)
    df.drop(columns=["REF", "ALT", "POS", "CHR_Length"], errors="ignore", inplace=True)

    # 10. Sauvegarde en PARQUET (Conserve les types de données mieux que le CSV)
    df.to_parquet(output_path, index=False)

    print(f"✅ Encodage terminé avec succès !")
    print(f"📊 Dataset final : {df.shape[0]} lignes | {df.shape[1]} colonnes")
    print(f"💾 Fichier sauvegardé : {output_path}")

if __name__ == "__main__":
    # Assure-toi que les chemins sont corrects pour ton WSL2
    RAW_PATH = "/home/badr/genomic-variant-mlops/data/processed/final_training_dataset.csv"
    OUT_PATH = "data/processed/genomic_variants_encoded.parquet"
    
    if os.path.exists(RAW_PATH):
        encode_genetic_features(RAW_PATH, OUT_PATH)
    else:
        print(f"❌ Erreur : Fichier introuvable à {RAW_PATH}")