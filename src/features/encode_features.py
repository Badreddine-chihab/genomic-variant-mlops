import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# Chromosome lengths (GRCh38)
CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415
}


def encode_genetic_features(input_path, output_path):

    print("🧬 Encoding (MLOps version)...")

    df = pd.read_csv(input_path)

    refs = df["REF"].astype(str)
    alts = df["ALT"].astype(str)
    chrom = df["CHROM"].astype(str)

    df["Target"] = df["Target"].astype("int8")

    # -----------------------------
    # Frequency Features (dbSNP)
    # -----------------------------
    df["population_frequency"] = df["ALT_FREQ"].astype("float32")
    df["rare_variant"] = (df["ALT_FREQ"] < 0.01).astype("int8")
    df["very_rare_variant"] = (df["ALT_FREQ"] < 0.001).astype("int8")

    # -----------------------------
    # Length + Impact
    # -----------------------------
    df["Delta_Length"] = (alts.str.len() - refs.str.len()).astype("int16")

    df["Impact_Score"] = (
        (df["Is_Frameshift"] * df["Delta_Length"].abs())
        / (df["ALT_FREQ"] + 1e-6)
    ).astype("float32")

    # -----------------------------
    # Position normalization
    # -----------------------------
    df["CHR_Length"] = chrom.map(CHR_LENGTHS)

    df["normalized_pos"] = (
        df["POS"] / df["CHR_Length"]
    ).astype("float32")

    # -----------------------------
    # Mutation Type
    # -----------------------------
    ref_base = refs.str[0].str.upper()
    alt_base = alts.str[0].str.upper()

    df["mutation_type"] = np.where(
        df["Is_InDel"] == 0,
        ref_base + "_" + alt_base,
        "INDEL"
    )

    # -----------------------------
    # Transition / Transversion
    # -----------------------------
    transition_pairs = {"A_G","G_A","C_T","T_C"}
    mutation_pair = ref_base + "_" + alt_base

    df["is_transition"] = mutation_pair.isin(transition_pairs).astype("int8")

    df["is_transversion"] = (
        (~mutation_pair.isin(transition_pairs)) &
        (df["Is_InDel"] == 0)
    ).astype("int8")

    # -----------------------------
    # Mutation Context
    # -----------------------------
    df["is_C_to_T"] = ((ref_base == "C") & (alt_base == "T")).astype("int8")
    df["is_G_to_A"] = ((ref_base == "G") & (alt_base == "A")).astype("int8")

    df["is_CpG_mutation"] = (
        (df["is_C_to_T"] == 1) | (df["is_G_to_A"] == 1)
    ).astype("int8")

    # -----------------------------
    # Scaling
    # -----------------------------
    scaler = StandardScaler()
    df[["ALT_FREQ","Delta_Length","Impact_Score"]] = scaler.fit_transform(
        df[["ALT_FREQ","Delta_Length","Impact_Score"]].astype("float32")
    )

    # -----------------------------
    # CATEGORICAL (XGBoost native)
    # -----------------------------
    df["CHROM"] = chrom.astype("category")
    df["REF_Base"] = ref_base.astype("category")
    df["ALT_Base"] = alt_base.astype("category")
    df["mutation_type"] = df["mutation_type"].astype("category")

    # -----------------------------
    # Cleanup
    # -----------------------------
    df = df.drop(columns=["REF","ALT","POS","CHR_Length"], errors="ignore")

    df.to_parquet(output_path, index=False)  # ⚡ mieux que CSV

    print("✅ Encoding done (categorical + optimized)")


if __name__ == "__main__":
    encode_genetic_features(
        input_path="/home/badr/genomic-variant-mlops/data/processed/final_training_dataset.csv",
        output_path="data/processed/genomic_variants_encoded.parquet"
    )