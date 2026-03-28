import polars as pl
import os

def optimize_dataset(input_path, output_path):
    print("🚀 Starting Data Optimization Pipeline...")
    
    # 1. Load Data
    df = pl.read_parquet(input_path)
    initial_rows, initial_cols = df.shape
    print(f"Initial shape: {initial_rows} rows, {initial_cols} columns")
    
    # 2. Handle Duplicates (High Priority)
    df = df.unique()
    print(f"Dropped {initial_rows - df.shape[0]} duplicate rows.")
    
    # 3. Handle Missing Values (High Priority)
    # We impute with -1.0 so XGBoost treats missingness as its own distinct numeric branch
    print("Imputing missing values for SIFT, PolyPhen, and CADD...")
    df = df.with_columns([
        pl.col("PolyPhen").fill_null(-1.0),
        pl.col("SIFT").fill_null(-1.0),
        pl.col("CADD").fill_null(-1.0)
    ])
    
    # 4. Handle Multicollinearity (High Priority)
    cols_to_drop = [
        "is_transversion",     # Perfect inverse of is_transition
        "freq_log",            # Redundant with ALT_FREQ
        "rare_impact",         # Redundant with Impact_Score
        "CADD_x_rare",         # High correlation with CADD
        "pos_bin",             # Redundant with normalized_pos
        "PolyPhen_damaging"    # Redundant binary indicator
    ]
    
    existing_drops = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(existing_drops)
    print(f"Dropped {len(existing_drops)} redundant features to fix multicollinearity.")

    # 5. Add Domain-Informed Features (Medium Priority)
    print("Adding advanced domain-informed interaction features...")
    df = df.with_columns([
        # Interaction: high-impact + rare
        ((pl.col("Impact_Score") > 0.7) & (pl.col("ALT_FREQ") < 0.01)).cast(pl.Int8).alias("high_impact_rare"),
        
        # Interaction: CADD + rarity 
        # Added 1e-9 to prevent division by zero for frequency = 0.0
        (pl.col("CADD") * (1.0 / (pl.col("ALT_FREQ") + 1e-9)).log1p()).cast(pl.Float32).alias("cadd_rare_interaction")
    ])

    # 6. Save Optimized Dataset
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.write_parquet(output_path)
    
    final_rows, final_cols = df.shape
    print("\n✅ Optimization complete!")
    print(f"📊 Final Dataset Shape: {final_rows} rows, {final_cols} columns")
    print(f"💾 Saved to: {output_path}")

if __name__ == "__main__":
    # Ensure working directory is set to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    IN_PATH = "/home/badr/genomic-variant-mlops/data/processed/final_training_dataset.parquet"
    OUT_PATH = "/home/badr/genomic-variant-mlops/data/processed/optimized_training_dataset.parquet"
    
    if os.path.exists(IN_PATH):
        optimize_dataset(IN_PATH, OUT_PATH)
    else:
        print(f"❌ Input file not found: {IN_PATH}")