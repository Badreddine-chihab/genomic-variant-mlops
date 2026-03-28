import polars as pl
import os

# -----------------------------
# Chromosome lengths (GRCh38)
# -----------------------------
CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415, "M": 16569
}

def encode_genetic_features(input_path, output_path):
    print("🧬 Smart Encoding Pipeline (Polars OOM-Safe Version)")

    # 1. Load and Map Columns
    column_mapping = {
        "#chr": "CHROM",
        "pos(1-based)": "POS",
        "ref": "REF",
        "alt": "ALT",
        "gnomAD_exomes_AF": "ALT_FREQ",
        "CADD_phred": "CADD",
        "SIFT_score": "SIFT",
        "Polyphen2_HDIV_score": "PolyPhen",
        "target": "Target"
    }

    # Reference DataFrame for chromosome lengths (using .lazy() to match input)
    chr_df = pl.DataFrame({
        "CHROM": list(CHR_LENGTHS.keys()),
        "CHR_Length": list(CHR_LENGTHS.values())
    }).with_columns(pl.col("CHROM").cast(pl.String)).lazy()

    # Lazy scan to protect RAM
    df = pl.scan_parquet(input_path).rename(column_mapping)

    # 2. Normalize chromosome format and Join Lengths
    df = (
        df.with_columns(pl.col("CHROM").str.replace("chr", ""))
        .join(chr_df, on="CHROM", how="inner")
    )

    # 3. Derive InDel and Frameshift flags dynamically
    df = df.with_columns([
        (pl.col("REF").str.len_bytes() != pl.col("ALT").str.len_bytes()).cast(pl.Int8).alias("Is_InDel"),
        (pl.col("ALT").str.len_bytes() - pl.col("REF").str.len_bytes()).cast(pl.Int16).alias("Delta_Length")
    ])

    df = df.with_columns([
        pl.col("Delta_Length").abs().cast(pl.Int16).alias("indel_size"),
        ((pl.col("Is_InDel") == 1) & (pl.col("Delta_Length").abs() % 3 != 0)).cast(pl.Int8).alias("Is_Frameshift")
    ])

    # 4. Base Extraction
    df = df.with_columns([
        pl.col("REF").str.slice(0, 1).str.to_uppercase().alias("REF_Base")
    ])

    df = df.with_columns([
        pl.when(pl.col("Is_InDel") == 0)
        .then(pl.col("ALT").str.slice(0, 1).str.to_uppercase())
        .otherwise(pl.lit("-"))
        .alias("ALT_Base")
    ])

    # 5. Mutation Type (Fixed string concatenation)
    df = df.with_columns([
        pl.when(pl.col("Is_InDel") == 0)
        .then(pl.concat_str([pl.col("REF_Base"), pl.lit("_"), pl.col("ALT_Base")]))
        .otherwise(pl.lit("INDEL"))
        .alias("mutation_type")
    ])

    # 6. Frequency Engineering
    df = df.with_columns([
        (pl.col("ALT_FREQ") + 1.0).log().cast(pl.Float32).alias("freq_log"),
        (pl.col("ALT_FREQ") < 0.005).cast(pl.Int8).alias("rare_variant"),
        (pl.col("ALT_FREQ") < 0.001).cast(pl.Int8).alias("is_ultra_rare"),
        (pl.col("indel_size") > 5).cast(pl.Int8).alias("is_large_indel")
    ])

    # 7. VEP-derived features (Fixed null filling with floats)
    df = df.with_columns([
        (pl.col("CADD").fill_null(0.0) > 20).cast(pl.Int8).alias("CADD_high"),
        (pl.col("CADD").fill_null(0.0) > 30).cast(pl.Int8).alias("CADD_very_high"),
        (pl.col("SIFT").fill_null(1.0) < 0.05).cast(pl.Int8).alias("SIFT_damaging"),
        (pl.col("PolyPhen").fill_null(0.0) > 0.8).cast(pl.Int8).alias("PolyPhen_damaging"),
    ])
    
    df = df.with_columns([
        (pl.col("CADD").fill_null(0.0) * pl.col("rare_variant")).cast(pl.Float32).alias("CADD_x_rare")
    ])

    # 8. Impact Score
    df = df.with_columns([
        (
            pl.col("Is_Frameshift") * 3 +
            pl.col("is_large_indel") * 2 +
            pl.col("indel_size") * 0.1 +
            pl.col("is_ultra_rare") * 2 +
            pl.col("CADD_high") * 2
        ).cast(pl.Float32).alias("Impact_Score")
    ])

    df = df.with_columns([
        (pl.col("rare_variant") * pl.col("Impact_Score")).cast(pl.Float32).alias("rare_impact")
    ])

    # 9. Genomic Position Features
    df = df.with_columns([
        (pl.col("POS") / pl.col("CHR_Length")).cast(pl.Float32).alias("normalized_pos")
    ])

    # Fixed qcut by replacing it with mathematical decile binning
    df = df.with_columns([
        (
            (pl.col("POS").rank("ordinal") - 1) / pl.col("POS").count() * 10
        ).cast(pl.Int8).over("CHROM").alias("pos_bin"),
        
        (pl.col("normalized_pos") * pl.col("freq_log")).cast(pl.Float32).alias("pos_freq_interaction")
    ])

    # 10. Transition / Transversion
    transition_pairs = ["A_G", "G_A", "C_T", "T_C"]
    df = df.with_columns([
        (pl.col("mutation_type").is_in(transition_pairs)).cast(pl.Int8).alias("is_transition"),
        (~pl.col("mutation_type").is_in(transition_pairs) & (pl.col("Is_InDel") == 0)).cast(pl.Int8).alias("is_transversion")
    ])

    # 11. Chromosome-level stats
    df = df.with_columns([
        pl.col("ALT_FREQ").mean().over("CHROM").cast(pl.Float32).alias("chrom_freq_mean"),
        pl.col("rare_variant").mean().over("CHROM").cast(pl.Float32).alias("chrom_rare_rate")
    ])

    # 12. Categorical Encoding & Cleanup
    cat_cols = ["CHROM", "REF_Base", "ALT_Base", "mutation_type"]
    df = df.with_columns([pl.col(c).cast(pl.Categorical) for c in cat_cols])

    df = df.drop(["REF", "ALT", "POS", "CHR_Length"])

    # 13. Execute Pipeline and Save
    print("Executing transformations and writing to disk...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    final_df = df.collect()
    final_df.write_parquet(output_path)

    print("\n📊 FINAL DATASET INFO:")
    print(f"Rows: {final_df.height}")
    print(f"Columns: {final_df.width}")
    print(f"\n✅ Saved to: {output_path}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    RAW_PATH = "/home/badr/genomic-variant-mlops/data/processed/model_ready_dataset.parquet"
    OUT_PATH = "/home/badr/genomic-variant-mlops/data/processed/final_training_dataset.parquet"
    
    if os.path.exists(RAW_PATH):
        encode_genetic_features(RAW_PATH, OUT_PATH)
    else:
        print(f"❌ File not found: {RAW_PATH}")