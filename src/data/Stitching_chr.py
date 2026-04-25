import polars as pl
import glob
import os
import shutil
import logging
import sys
from pathlib import Path
from src.orchestration.config_utils import ConfigManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Colonnes nécessaires pour le modèle
FEATURES = [
    "#chr", "pos(1-based)", "ref", "alt", 
    "SIFT_score", "Polyphen2_HDIV_score", "CADD_phred", 
    "gnomAD_exomes_AF", "clinvar_clnsig"
]

def extract_and_stitch_data(cfg):
    """Extraction et assemblage des chromosomes via Polars Streaming."""
    # Utilisation du ConfigManager pour résoudre les chemins proprement
    cm = ConfigManager()
    raw_dir = cm.get_path("paths.data.raw_dir")
    processed_dir = cm.get_path("paths.data.processed_dir")
    final_output = cm.get_path("paths.data.model_ready")
    
    temp_dir = processed_dir / "temp_streaming"
    temp_dir.mkdir(parents=True, exist_ok=True)
    final_output.parent.mkdir(parents=True, exist_ok=True)

    # Recherche des fichiers (DVC doit les avoir 'pull' avant ce script)
    gz_files = sorted(glob.glob(str(raw_dir / "dbNSFP4.9a_variant.chr*.gz")))
    
    if not gz_files:
        logger.error(f"❌ Aucun fichier .gz trouvé dans {raw_dir}. As-tu fait un 'dvc pull' ?")
        sys.exit(1)

    logger.info(f"🚀 Début du traitement de {len(gz_files)} chromosomes...")

    for filepath in gz_files:
        chr_name = Path(filepath).name.split('.')[2]
        temp_raw = temp_dir / f"{chr_name}_raw.parquet"
        temp_clean = temp_dir / f"{chr_name}_clean.parquet"
        
        logger.info(f"📦 Processing {chr_name}...")

        try:
            # STEP A: Streaming CSV -> Parquet (OOM Safe)
            (
                pl.scan_csv(
                    filepath, 
                    separator="\t", 
                    ignore_errors=True, 
                    schema_overrides={
                        "#chr": pl.String, "CADD_phred": pl.String, 
                        "SIFT_score": pl.String, "Polyphen2_HDIV_score": pl.String, 
                        "gnomAD_exomes_AF": pl.String
                    }
                )
                .select(FEATURES)
                .filter(pl.col("clinvar_clnsig").is_not_null() & (pl.col("clinvar_clnsig") != ""))
                .sink_parquet(str(temp_raw))
            )

            # STEP B: Nettoyage et Target Encoding
            df = pl.read_parquet(str(temp_raw))
            df = (
                df.with_columns(pl.col("clinvar_clnsig").str.to_lowercase().alias("clinvar_lower"))
                .with_columns([
                    pl.when(pl.col("clinvar_lower").str.contains("pathogenic")).then(1)
                    .when(pl.col("clinvar_lower").str.contains("benign")).then(0)
                    .otherwise(None).alias("target")
                ])
                .filter(pl.col("target").is_not_null())
            )

            if len(df) > 0:
                cols_to_clean = ["SIFT_score", "Polyphen2_HDIV_score", "CADD_phred", "gnomAD_exomes_AF"]
                for col in cols_to_clean:
                    df = df.with_columns(
                        pl.col(col).str.split(";").list.first().cast(pl.Float32, strict=False)
                    )
                
                df = df.with_columns(pl.col("gnomAD_exomes_AF").fill_null(0.0))
                df = df.drop(["clinvar_clnsig", "clinvar_lower"])
                df.write_parquet(str(temp_clean))
            
            temp_raw.unlink() # Libère l'espace disque immédiatement

        except Exception as e:
            logger.warning(f"⚠️ Erreur sur {chr_name}: {e}")
            continue

    # --- FINAL STITCHING ---
    clean_files = sorted(temp_dir.glob("*_clean.parquet"))
    if clean_files:
        logger.info(f"🧵 Assemblage final vers : {final_output}")
        final_df = pl.read_parquet([str(f) for f in clean_files])
        final_df.write_parquet(str(final_output))
        logger.info(f"✅ Terminé ! Total rows: {len(final_df)}")
        
        # LIBÉRATION ESPACE : On supprime les fichiers temporaires
        shutil.rmtree(str(temp_dir))
        
        # OPTIONNEL : Supprimer les .gz originaux pour gagner de la place
        # for f in gz_files: os.remove(f) 
    else:
        logger.error("❌ Échec : Aucun fichier clean n'a été généré.")
        sys.exit(1)

if __name__ == "__main__":
    cm = ConfigManager()
    extract_and_stitch_data(cm.config)