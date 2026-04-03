import polars as pl
import glob
import os
import shutil

# --- 1. SMART PATH CONFIGURATION ---
# Automatically sets the working directory to where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Define the columns needed for the machine learning model
features = [
    "#chr", "pos(1-based)", "ref", "alt", 
    "SIFT_score", "Polyphen2_HDIV_score", "CADD_phred", 
    "gnomAD_exomes_AF", "clinvar_clnsig"
]

temp_dir = "../processed/temp_streaming"
final_output = "../processed/model_ready_dataset.parquet"

# Create directories safely
os.makedirs(temp_dir, exist_ok=True)
os.makedirs("../processed", exist_ok=True)

gz_files = sorted(glob.glob("dbNSFP4.9a_variant.chr*.gz"))

if not gz_files:
    print(f"❌ ERROR: No .gz files found in {script_dir}")
    exit()

print(f"Found {len(gz_files)} files. Starting extraction pipeline...")

# --- 2. EXTRACTION & CLEANING LOOP ---
for filepath in gz_files:
    chr_name = filepath.split('.')[2]
    temp_raw = os.path.join(temp_dir, f"{chr_name}_raw.parquet")
    temp_clean = os.path.join(temp_dir, f"{chr_name}_clean.parquet")
    
    print(f"Processing {chr_name}...")
    
    # STEP A: Stream directly to disk (Bypasses RAM limits & fixes schema crashes)
    try:
        (
            pl.scan_csv(
                filepath, 
                separator="\t", 
                ignore_errors=True, 
                schema_overrides={
                    "#chr": pl.String, 
                    "CADD_phred": pl.String, 
                    "SIFT_score": pl.String, 
                    "Polyphen2_HDIV_score": pl.String, 
                    "gnomAD_exomes_AF": pl.String
                }
            )
            .select(features)
            .filter(pl.col("clinvar_clnsig").is_not_null() & (pl.col("clinvar_clnsig") != ""))
            .sink_parquet(temp_raw)
        )
    except Exception as e:
        print(f"   ⚠️ Skipping {chr_name} due to error: {e}")
        continue

    # STEP B: Preprocess the extracted chunk
    if os.path.exists(temp_raw) and os.path.getsize(temp_raw) > 0:
        df = pl.read_parquet(temp_raw)
        
        # Encode Target: Pathogenic = 1, Benign = 0
        df = (
            df
            .with_columns(pl.col("clinvar_clnsig").str.to_lowercase().alias("clinvar_lower"))
            .with_columns([
                pl.when(pl.col("clinvar_lower").str.contains("pathogenic")).then(1)
                .when(pl.col("clinvar_lower").str.contains("benign")).then(0)
                .otherwise(None)
                .alias("target")
            ])
            .filter(pl.col("target").is_not_null())
        )

        if len(df) > 0:
            # Clean semicolons from numerical scores
            cols_to_clean = ["SIFT_score", "Polyphen2_HDIV_score", "CADD_phred", "gnomAD_exomes_AF"]
            for col in cols_to_clean:
                df = df.with_columns(
                    pl.col(col).str.split(";").list.first().cast(pl.Float32, strict=False)
                )
            
            # Impute missing frequencies with 0.0 and drop text columns
            df = df.with_columns(pl.col("gnomAD_exomes_AF").fill_null(0.0))
            df = df.drop(["clinvar_clnsig", "clinvar_lower"])
            
            # Save the clean chunk
            df.write_parquet(temp_clean)
            print(f"   -> Saved {len(df)} variants.")
        
        # Delete the raw temp file to save SSD space
        os.remove(temp_raw)

# --- 3. FINAL STITCHING ---
clean_files = glob.glob(os.path.join(temp_dir, "*_clean.parquet"))

if not clean_files:
    print("\n❌ Error: No clean parquet files were created.")
else:
    print(f"\nStitching {len(clean_files)} files into the final dataset...")
    
    # Read all clean chunks and combine them
    final_df = pl.read_parquet(clean_files)
    final_df.write_parquet(final_output)
    
    print(f"✅ SUCCESS! Final dataset saved to: {final_output}")
    print(f"Total model-ready rows: {len(final_df)}")
    
    # Clean up the temporary directory
    shutil.rmtree(temp_dir)