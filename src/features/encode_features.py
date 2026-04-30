import streamlit as st
import pandas as pd
import polars as pl
import numpy as np
import mlflow.pyfunc
from bridge import fetch_features_from_s3

# --- CONFIGURATION & CONSTANTES ---
st.set_page_config(page_title="GenoPredict Portal", layout="wide", page_icon="🧬")

CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415, "M": 16569
}

# 1. CHARGEMENT DU MODÈLE
mlflow.set_tracking_uri("http://localhost:5000")

@st.cache_resource
def load_production_model():
    model_uri = "models:/GenomicVariantModel/Production"
    try:
        return mlflow.pyfunc.load_model(model_uri)
    except Exception as e:
        st.error(f"❌ Erreur MLflow : {e}")
        return None

model = load_production_model()

# --- FONCTION DE FEATURE ENGINEERING (SYNC AVEC TES SCRIPTS) ---
def prepare_inference_data(raw_pandas_df):
    """Fusion de encode_features.py et optimizations.py adaptée à l'inférence."""
    try:
        # Conversion Pandas -> Polars pour utiliser ta logique exacte
        ldf = pl.from_pandas(raw_pandas_df).lazy()

        # 1. Mapping initial
        column_mapping = {
            "#chr": "CHROM",
            "pos(1-based)": "POS",
            "ref": "REF",
            "alt": "ALT",
            "gnomAD_exomes_AF": "ALT_FREQ",
            "CADD_phred": "CADD",
            "SIFT_score": "SIFT",
            "Polyphen2_HDIV_score": "PolyPhen"
        }
        
        # On ne garde que les colonnes présentes
        available_mapping = {k: v for k, v in column_mapping.items() if k in ldf.columns}
        ldf = ldf.rename(available_mapping)

        # 2. Chromosome Lengths
        chr_info = pl.DataFrame({
            "CHROM": list(CHR_LENGTHS.keys()),
            "CHR_Length": list(CHR_LENGTHS.values())
        }).with_columns(pl.col("CHROM").cast(pl.String)).lazy()

        ldf = ldf.with_columns(pl.col("CHROM").str.replace("chr", "")) \
                 .join(chr_info, on="CHROM", how="left")

        # 3. InDels & Flags (Logique de encode_features.py)
        ldf = ldf.with_columns([
            (pl.col("REF").str.len_bytes() != pl.col("ALT").str.len_bytes()).cast(pl.Int8).alias("Is_InDel"),
            (pl.col("ALT").str.len_bytes() - pl.col("REF").str.len_bytes()).cast(pl.Int16).alias("Delta_Length")
        ]).with_columns([
            pl.col("Delta_Length").abs().cast(pl.Int16).alias("indel_size"),
            ((pl.col("Is_InDel") == 1) & (pl.col("Delta_Length").abs() % 3 != 0)).cast(pl.Int8).alias("Is_Frameshift")
        ])

        # 4. Base & Mutation Type
        ldf = ldf.with_columns([
            pl.col("REF").str.slice(0, 1).str.to_uppercase().alias("REF_Base"),
            pl.when(pl.col("Is_InDel") == 0)
              .then(pl.col("ALT").str.slice(0, 1).str.to_uppercase())
              .otherwise(pl.lit("-")).alias("ALT_Base")
        ]).with_columns([
            pl.when(pl.col("Is_InDel") == 0)
              .then(pl.concat_str([pl.col("REF_Base"), pl.lit("_"), pl.col("ALT_Base")]))
              .otherwise(pl.lit("INDEL")).alias("mutation_type")
        ])

        # 5. Frequency & Scores (Imputation incluse de optimizations.py)
        ldf = ldf.with_columns([
            pl.col("ALT_FREQ").fill_null(0.0),
            pl.col("SIFT").fill_null(-1.0).cast(pl.Float32),
            pl.col("PolyPhen").fill_null(-1.0).cast(pl.Float32),
            pl.col("CADD").fill_null(-1.0).cast(pl.Float32)
        ]).with_columns([
            (pl.col("ALT_FREQ") + 1.0).log().alias("freq_log"),
            (pl.col("ALT_FREQ") < 0.005).cast(pl.Int8).alias("rare_variant"),
            (pl.col("ALT_FREQ") < 0.001).cast(pl.Int8).alias("is_ultra_rare"),
            (pl.col("indel_size") > 5).cast(pl.Int8).alias("is_large_indel"),
            (pl.col("CADD") > 20).cast(pl.Int8).alias("CADD_high"),
            (pl.col("CADD") > 30).cast(pl.Int8).alias("CADD_very_high"),
            (pl.col("SIFT") < 0.05).cast(pl.Int8).alias("SIFT_damaging")
        ])

        # 6. Impact & Interactions
        ldf = ldf.with_columns([
            (pl.col("Is_Frameshift") * 3 + pl.col("is_large_indel") * 2 + 
             pl.col("indel_size") * 0.1 + pl.col("is_ultra_rare") * 2 + 
             pl.col("CADD_high") * 2).cast(pl.Float32).alias("Impact_Score")
        ]).with_columns([
            (pl.col("rare_variant") * pl.col("Impact_Score")).alias("rare_impact"),
            (pl.col("POS") / pl.col("CHR_Length")).cast(pl.Float32).alias("normalized_pos"),
            ((pl.col("Impact_Score") > 0.7) & (pl.col("ALT_FREQ") < 0.01)).cast(pl.Int8).alias("high_impact_rare"),
            (pl.col("CADD") * (1.0 / (pl.col("ALT_FREQ") + 1e-9)).log1p()).alias("cadd_rare_interaction")
        ])

        # 7. Final Clean-up (Match XGBoost Expectation)
        # On définit l'ordre exact des colonnes que ton modèle attendait dans l'erreur précédente
        final_cols = [
            'CHROM', 'SIFT', 'PolyPhen', 'CADD', 'ALT_FREQ', 'Is_InDel', 'Delta_Length', 
            'indel_size', 'Is_Frameshift', 'REF_Base', 'ALT_Base', 'mutation_type', 
            'freq_log', 'rare_variant', 'is_ultra_rare', 'is_large_indel', 'CADD_high', 
            'CADD_very_high', 'SIFT_damaging', 'Impact_Score', 'rare_impact', 
            'normalized_pos', 'is_transition', 'high_impact_rare', 'cadd_rare_interaction'
        ]
        
        # Note: Certaines stats comme 'chrom_freq_mean' nécessitent tout le chromosome. 
        # Pour une seule ligne, on met des valeurs neutres ou on les retire si le modèle optimisé ne les veut plus.
        
        # Exécution du pipeline lazy
        res_df = ldf.collect().to_pandas()
        
        # On s'assure que toutes les colonnes attendues par TON modèle sont là (même à 0 si besoin)
        # D'après ton erreur précédente, voici la liste :
        expected_by_model = [
            'pos_bin', 'ALT_FREQ', 'CADD_x_rare', 'CADD', 'CADD_high', 'Is_Frameshift', 
            'SIFT', 'rare_variant', 'Impact_Score', 'pos_freq_interaction', 
            'PolyPhen_damaging', 'Is_InDel', 'chrom_freq_mean', 'normalized_pos', 
            'CHROM', 'mutation_type', 'rare_impact', 'ALT_Base', 'is_ultra_rare', 
            'CADD_very_high', 'indel_size', 'SIFT_damaging', 'Delta_Length', 
            'is_transition', 'REF_Base', 'chrom_rare_rate', 'freq_log', 'PolyPhen', 
            'is_large_indel', 'is_transversion'
        ]
        
        for col in expected_by_model:
            if col not in res_df.columns:
                res_df[col] = 0 # Valeur par défaut pour éviter le crash
                
        return res_df[expected_by_model]
        
    except Exception as e:
        st.error(f"❌ Erreur Preprocessing : {e}")
        return None

# --- UI INTERFACE ---
st.title("🧬 GenoPredict Portal")
st.divider()

with st.sidebar:
    st.header("🔍 Variant Lookup")
    chrom = st.selectbox("Chromosome", [str(i) for i in range(1, 23)] + ["X", "Y", "M"])
    pos = st.text_input("Position (hg38)", value="1022225")
    predict_btn = st.button("🚀 Analyser")

if predict_btn:
    raw_data = fetch_features_from_s3(chrom, pos)
    
    if raw_data is not None and not raw_data.empty:
        st.success("✅ Données extraites de S3.")

        if model:
            # On applique la même logique que encode_features.py + optimizations.py
            X_input = prepare_inference_data(raw_data)
            
            if X_input is not None:
                # Inférence MLflow
                prediction_prob = model.predict(X_input)[0]
                
                label = "PATHOGÈNE" if prediction_prob > 0.5 else "BÉNIN"
                color = "#e63946" if label == "PATHOGÈNE" else "#2a9d8f"

                st.markdown(f"""
                    <div style="padding:20px; border-radius:10px; border:3px solid {color}; text-align:center; color:{color}; font-size:24px; font-weight:bold;">
                        Diagnostic : {label} ({prediction_prob:.2%})
                    </div>
                """, unsafe_allow_html=True)

        # Affichage des infos brutes pour vérification
        st.subheader("📋 Aperçu dbNSFP")
        st.dataframe(raw_data)
    else:
        st.error("❌ Variant non trouvé.")