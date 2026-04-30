import os

import streamlit as st
import pandas as pd
import polars as pl
import numpy as np
import mlflow.pyfunc
from scripts.bridge import fetch_features_from_s3

# ==========================================
# 1. CONFIGURATION ET CONSTANTES
# ==========================================
st.set_page_config(page_title="GenoPredict | MLOps Pipeline", layout="wide")

CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415, "M": 16569
}

ORDERED_FEATURES = [
    'CHROM', 'SIFT', 'PolyPhen', 'CADD', 'ALT_FREQ', 'Is_InDel', 
    'Delta_Length', 'indel_size', 'Is_Frameshift', 'REF_Base', 
    'ALT_Base', 'mutation_type', 'freq_log', 'rare_variant', 
    'is_ultra_rare', 'is_large_indel', 'CADD_high', 'CADD_very_high', 
    'SIFT_damaging', 'PolyPhen_damaging', 'CADD_x_rare', 'Impact_Score', 
    'rare_impact', 'normalized_pos', 'pos_bin', 'pos_freq_interaction', 
    'is_transition', 'is_transversion', 'chrom_freq_mean', 'chrom_rare_rate'
]

# ==========================================
# 2. INITIALISATION DE L'ÉTAT
# ==========================================
if 'ui_state' not in st.session_state:
    st.session_state.ui_state = 'init'
if 'target_variant_df' not in st.session_state:
    st.session_state.target_variant_df = None

# ==========================================
# 3. FONCTIONS CŒUR
# ==========================================
@st.cache_resource(show_spinner=False)
def load_mlflow_model():
    import os
# Utilise l'environnement Docker si disponible, sinon localhost
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    try:
        return mlflow.pyfunc.load_model("models:/GenomicVariantModel@Production")
    except Exception as e:
        st.error(f"Erreur d'initialisation du modèle MLflow: {e}")
        return None

def preprocess_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    try:
        ldf = pl.from_pandas(df_raw).lazy()
        
        col_mapping = {
            "#chr": "CHROM", "pos(1-based)": "POS", "ref": "REF", "alt": "ALT",
            "gnomAD_exomes_AF": "ALT_FREQ", "CADD_phred": "CADD",
            "SIFT_score": "SIFT", "Polyphen2_HVAR_score": "PolyPhen"
        }
        ldf = ldf.rename({k: v for k, v in col_mapping.items() if k in ldf.columns})

        num_cols = ["ALT_FREQ", "CADD", "SIFT", "PolyPhen", "POS"]
        for c in num_cols:
            if c in ldf.collect_schema().names():
                ldf = ldf.with_columns(
                    pl.col(c).cast(pl.Utf8).str.replace(",", ".").cast(pl.Float32, strict=False).fill_null(0.0)
                )

        ldf = ldf.with_columns([
            pl.col("CHROM").cast(pl.Utf8).str.replace("chr", ""),
            (pl.col("REF").str.len_bytes() != pl.col("ALT").str.len_bytes()).cast(pl.Int8).alias("Is_InDel"),
            (pl.col("ALT").str.len_bytes() - pl.col("REF").str.len_bytes()).cast(pl.Int16).alias("Delta_Length")
        ]).with_columns([
            pl.col("Delta_Length").abs().alias("indel_size"),
            ((pl.col("Is_InDel") == 1) & (pl.col("Delta_Length").abs() % 3 != 0)).cast(pl.Int8).alias("Is_Frameshift")
        ])

        ldf = ldf.with_columns([
            (pl.col("ALT_FREQ") + 1e-9).log().alias("freq_log"),
            (pl.col("ALT_FREQ") < 0.005).cast(pl.Int8).alias("rare_variant"),
            pl.col("CADD").fill_null(-1.0), 
            pl.col("SIFT").fill_null(-1.0), 
            pl.col("PolyPhen").fill_null(-1.0)
        ]).with_columns([
            (pl.col("CADD") > 20).cast(pl.Int8).alias("CADD_high"),
            (pl.col("CADD") > 30).cast(pl.Int8).alias("CADD_very_high"),
            (pl.col("SIFT") < 0.05).cast(pl.Int8).alias("SIFT_damaging"),
            (pl.col("PolyPhen") > 0.8).cast(pl.Int8).alias("PolyPhen_damaging"),
            (pl.col("indel_size") > 5).cast(pl.Int8).alias("is_large_indel"),
            (pl.col("ALT_FREQ") < 0.001).cast(pl.Int8).alias("is_ultra_rare")
        ])

        df_processed = ldf.collect().to_pandas()
        
        df_processed['REF_Base'] = df_processed['REF'].str[0]
        df_processed['ALT_Base'] = np.where(df_processed['Is_InDel'] == 0, df_processed['ALT'].str[0], "-")
        df_processed['mutation_type'] = np.where(df_processed['Is_InDel'] == 0, df_processed['REF_Base'] + "_" + df_processed['ALT_Base'], "INDEL")
        
        df_processed['is_transition'] = df_processed['mutation_type'].isin(["A_G", "G_A", "C_T", "T_C"]).astype(int)
        df_processed['is_transversion'] = ((df_processed['Is_InDel'] == 0) & (~df_processed['is_transition'].astype(bool))).astype(int)
        
        df_processed['Impact_Score'] = (df_processed['Is_Frameshift'] * 3 + df_processed['is_large_indel'] * 2 + df_processed['is_ultra_rare'] * 2).astype(float)
        df_processed['rare_impact'] = df_processed['rare_variant'] * df_processed['Impact_Score']
        df_processed['CADD_x_rare'] = df_processed['CADD'] * df_processed['rare_variant']
        
        df_processed['normalized_pos'] = df_processed['POS'].astype(float) / df_processed['CHROM'].map(CHR_LENGTHS).fillna(2e8)
        df_processed['pos_freq_interaction'] = df_processed['normalized_pos'] * df_processed['ALT_FREQ']
        df_processed['pos_bin'] = 5
        df_processed['chrom_rare_rate'] = 0.5
        df_processed['chrom_freq_mean'] = 0.001

        categorical_cols = ['ALT_Base', 'mutation_type', 'REF_Base', 'CHROM']
        for col in categorical_cols:
            df_processed[col] = df_processed[col].astype('category')

        return df_processed[ORDERED_FEATURES]

    except Exception as e:
        raise RuntimeError(f"Erreur lors du feature engineering: {str(e)}")

# ==========================================
# 4. INTERFACE UTILISATEUR
# ==========================================
st.title("Système d'Inférence - Variants Génomiques")
model = load_mlflow_model()

with st.sidebar:
    st.header("Paramètres de Requête")
    with st.form("search_form"):
        chrom_in = st.selectbox("Chromosome", [str(i) for i in range(1, 23)] + ["X", "Y"])
        pos_in = st.text_input("Position", value="209271")
        ref_in = st.text_input("Référence (REF)", value="C").strip().upper()
        alt_in = st.text_input("Altération (ALT)", value="A").strip().upper()
        submit_search = st.form_submit_button("Interroger le Feature Store", use_container_width=True)

if submit_search:
    with st.spinner("Extraction depuis DuckDB/S3..."):
        raw_data = fetch_features_from_s3(chrom_in, pos_in, ref_in, alt_in)
        
        if raw_data is not None and not raw_data.empty:
            raw_data['ref_clean'] = raw_data['ref'].astype(str).str.strip().str.upper()
            raw_data['alt_clean'] = raw_data['alt'].astype(str).str.strip().str.upper()
            
            match = raw_data[(raw_data['ref_clean'] == ref_in) & (raw_data['alt_clean'] == alt_in)]
            
            if not match.empty:
                st.session_state.target_variant_df = match.head(1).drop(columns=['ref_clean', 'alt_clean'])
                st.session_state.ui_state = 'S3_found'
            else:
                st.session_state.ui_state = 'manual_needed'
                st.warning("Position trouvée dans le Feature Store, mais les allèles ne correspondent pas.")
        else:
            st.session_state.ui_state = 'manual_needed'
            st.info("Variant introuvable dans le Feature Store actuel.")

# ==========================================
# 5. GESTION DES FLUX (MANUEL / INFERENCE)
# ==========================================
if st.session_state.ui_state == 'manual_needed':
    st.divider()
    st.subheader("Saisie Biologique (Fallback)")
    with st.form("manual_form"):
        cols = st.columns(4)
        m_sift = cols[0].number_input("SIFT_score", 0.0, 1.0, 0.05)
        m_poly = cols[1].number_input("Polyphen2_HVAR_score", 0.0, 1.0, 0.85)
        m_cadd = cols[2].number_input("CADD_phred", 0.0, 60.0, 25.0)
        m_af = cols[3].number_input("gnomAD_exomes_AF", 0.0, 1.0, 0.0001, format="%.6f")
        
        if st.form_submit_button("Lancer la prédiction manuelle"):
            st.session_state.target_variant_df = pd.DataFrame([{ 
                "#chr": chrom_in, "pos(1-based)": pos_in, "ref": ref_in, "alt": alt_in,
                "SIFT_score": m_sift, "Polyphen2_HVAR_score": m_poly, 
                "CADD_phred": m_cadd, "gnomAD_exomes_AF": m_af 
            }])
            st.session_state.ui_state = 'ready_to_predict'

if st.session_state.ui_state in ['S3_found', 'ready_to_predict'] and st.session_state.target_variant_df is not None:
    st.divider()
    st.subheader("Résultat du Modèle")
    
    if model is None:
        st.error("Inférence impossible : Modèle non chargé.")
    else:
        try:
            X_vector = preprocess_features(st.session_state.target_variant_df)
            raw_prediction = model.predict(X_vector)
            
            # Résolution dynamique
            pred_value = raw_prediction[0] if isinstance(raw_prediction, (np.ndarray, list)) else raw_prediction
            if isinstance(pred_value, pd.Series):
                pred_value = pred_value.iloc[0]
            
            pred_value = float(pred_value)
            is_class_output = (pred_value == 0.0 or pred_value == 1.0)
            
            if is_class_output:
                is_pathogenic = (pred_value == 1.0)
                display_text = "PATHOGÈNE" if is_pathogenic else "BÉNIN"
            else:
                is_pathogenic = (pred_value > 0.5)
                display_text = f"PATHOGÈNE ({pred_value:.2%})" if is_pathogenic else f"BÉNIN ({pred_value:.2%})"

            color = "#8b0000" if is_pathogenic else "#006400"
            st.markdown(f"""
                <div style="background-color:{color}; color:white; padding:20px; border-radius:5px; text-align:center; font-size:24px; font-weight:bold;">
                    {display_text}
                </div>
            """, unsafe_allow_html=True)
            
            st.write("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("CADD Phred", f"{X_vector['CADD'].iloc[0]:.2f}")
            m2.metric("Fréquence (AF)", f"{X_vector['ALT_FREQ'].iloc[0]:.6f}")
            m3.metric("Mutation", str(X_vector['mutation_type'].iloc[0]))
            m4.metric("Type de retour", "Classe binaire" if is_class_output else "Probabilité")

        except Exception as e:
            st.error(f"Erreur fatale lors de l'inférence : {str(e)}")