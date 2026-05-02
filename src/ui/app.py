import os
import streamlit as st
import pandas as pd
import polars as pl
import numpy as np
import mlflow
import mlflow.pyfunc

from scripts.bridge import fetch_features_from_s3

# ==========================================
# 🎨 CONFIG + STYLE
# ==========================================
st.set_page_config(page_title="GenoPredict", layout="wide")

st.markdown("""
<style>
.main {background-color: #0e1117;}
.block-container {padding-top: 2rem;}

.title {font-size: 36px; font-weight: 700; color: white;}
.subtitle {color: #9ca3af; font-size: 16px;}

.card {
    background: #161b22;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #30363d;
    margin-bottom: 20px;
}

.metric-card {
    background: linear-gradient(135deg, #1f2937, #111827);
    padding: 15px;
    border-radius: 10px;
    text-align: center;
}

.result-box {
    padding: 25px;
    border-radius: 12px;
    text-align: center;
    font-size: 26px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧬 CONSTANTS
# ==========================================
CHR_LENGTHS = {
    "1":248956422,"2":242193529,"3":198295559,"4":190214555,"5":181538259,
    "6":170805979,"7":159345973,"8":145138636,"9":138394717,"10":133797422,
    "11":135086622,"12":133275309,"13":114364328,"14":107043718,"15":101991189,
    "16":90338345,"17":83257441,"18":80373285,"19":58617616,"20":64444167,
    "21":46709983,"22":50818468,"X":156040895,"Y":57227415,"M":16569
}

ORDERED_FEATURES = [
    'CHROM','SIFT','PolyPhen','CADD','ALT_FREQ','Is_InDel','Delta_Length',
    'indel_size','Is_Frameshift','REF_Base','ALT_Base','mutation_type',
    'freq_log','rare_variant','is_ultra_rare','is_large_indel','CADD_high',
    'CADD_very_high','SIFT_damaging','PolyPhen_damaging','CADD_x_rare',
    'Impact_Score','rare_impact','normalized_pos','pos_bin',
    'pos_freq_interaction','is_transition','is_transversion',
    'chrom_freq_mean','chrom_rare_rate'
]

DEFAULT_FEATURE_VALUES = {
    "SIFT": -1.0,
    "PolyPhen": -1.0,
    "CADD": -1.0,
    "ALT_FREQ": 0.0,
    "POS": 0.0,
    "CHROM": "1",
    "REF": "N",
    "ALT": "N",
}

NUMERIC_DEFAULTS = {
    "Is_InDel": 0,
    "Delta_Length": 0,
    "indel_size": 0,
    "Is_Frameshift": 0,
    "freq_log": 0.0,
    "rare_variant": 0,
    "is_ultra_rare": 0,
    "is_large_indel": 0,
    "CADD_high": 0,
    "CADD_very_high": 0,
    "SIFT_damaging": 0,
    "PolyPhen_damaging": 0,
    "CADD_x_rare": 0.0,
    "Impact_Score": 0.0,
    "rare_impact": 0.0,
    "normalized_pos": 0.0,
    "pos_bin": 0,
    "pos_freq_interaction": 0.0,
    "is_transition": 0,
    "is_transversion": 0,
    "chrom_freq_mean": 0.0,
    "chrom_rare_rate": 0.0,
}

CATEGORICAL_DEFAULTS = {
    "REF_Base": "N",
    "ALT_Base": "N",
    "mutation_type": "N_N",
}

# ==========================================
# 🧠 SESSION STATE
# ==========================================
if 'ui_state' not in st.session_state:
    st.session_state.ui_state = 'init'

if 'target_variant_df' not in st.session_state:
    st.session_state.target_variant_df = None

# ==========================================
# 🤖 LOAD MODEL
# ==========================================
@st.cache_resource
def load_model():
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)

    try:
        return mlflow.pyfunc.load_model("models:/GenomicVariantModel@Production")
    except Exception as e:
        st.error(f"MLflow error: {e}")
        return None

# ==========================================
# 🔬 PREPROCESS
# ==========================================
def preprocess_features(df_raw):

    ldf = pl.from_pandas(df_raw).lazy()

    col_mapping = {
        "#chr":"CHROM","pos(1-based)":"POS","ref":"REF","alt":"ALT",
        "gnomAD_exomes_AF":"ALT_FREQ","CADD_phred":"CADD",
        "SIFT_score":"SIFT","Polyphen2_HVAR_score":"PolyPhen"
    }

    ldf = ldf.rename({k:v for k,v in col_mapping.items() if k in ldf.columns})
    schema_names = set(ldf.collect_schema().names())

    missing_base = {k: v for k, v in DEFAULT_FEATURE_VALUES.items() if k not in schema_names}
    if missing_base:
        ldf = ldf.with_columns([pl.lit(v).alias(k) for k, v in missing_base.items()])

    for c in ["ALT_FREQ","CADD","SIFT","PolyPhen","POS"]:
        if c in ldf.collect_schema().names():
            ldf = ldf.with_columns(
                pl.col(c).cast(pl.Float32, strict=False).fill_null(0.0)
            )

    ldf = ldf.with_columns([
        (pl.col("REF").str.len_bytes() != pl.col("ALT").str.len_bytes()).cast(pl.Int8).alias("Is_InDel"),
        (pl.col("ALT").str.len_bytes() - pl.col("REF").str.len_bytes()).alias("Delta_Length")
    ])

    df = ldf.collect().to_pandas()

    df["REF_Base"] = df["REF"].str[0]
    df["ALT_Base"] = df["ALT"].str[0]
    df["mutation_type"] = df["REF_Base"] + "_" + df["ALT_Base"]

    df["indel_size"] = df["Delta_Length"].abs().astype(float)
    df["Is_Frameshift"] = ((df["Is_InDel"] == 1) & ((df["indel_size"] % 3) != 0)).astype(int)
    df["freq_log"] = np.log1p(df["ALT_FREQ"].astype(float))
    df["rare_variant"] = (df["ALT_FREQ"] < 0.005).astype(int)
    df["is_ultra_rare"] = (df["ALT_FREQ"] < 0.001).astype(int)
    df["is_large_indel"] = (df["indel_size"] > 5).astype(int)
    df["CADD_high"] = (df["CADD"] > 20).astype(int)
    df["CADD_very_high"] = (df["CADD"] > 30).astype(int)
    df["SIFT_damaging"] = (df["SIFT"] < 0.05).astype(int)
    df["PolyPhen_damaging"] = (df["PolyPhen"] > 0.85).astype(int)
    df["CADD_x_rare"] = df["CADD"].astype(float) * (1.0 - df["ALT_FREQ"].clip(0.0, 1.0))

    df["Impact_Score"] = (
        df["Is_Frameshift"] * 3.0
        + df["is_large_indel"] * 2.0
        + df["indel_size"] * 0.1
        + df["is_ultra_rare"] * 2.0
        + df["CADD_high"] * 2.0
    ).astype(float)
    df["rare_impact"] = df["rare_variant"] * df["Impact_Score"]
    chrom_lengths = df["CHROM"].astype(str).map(CHR_LENGTHS).fillna(2e8)
    df["normalized_pos"] = (df["POS"].astype(float) / chrom_lengths).astype(float)
    df["pos_bin"] = pd.cut(
        df["normalized_pos"].clip(lower=0.0),
        bins=[-0.001, 0.25, 0.5, 0.75, 1.0, np.inf],
        labels=[0, 1, 2, 3, 4]
    ).astype(int)
    df["pos_freq_interaction"] = df["normalized_pos"] * df["ALT_FREQ"].astype(float)

    is_snp = (df["REF"].str.len() == 1) & (df["ALT"].str.len() == 1)
    transitions = {"A_G", "G_A", "C_T", "T_C"}
    mutation_pairs = (df["REF_Base"] + "_" + df["ALT_Base"]).astype(str)
    df["is_transition"] = (is_snp & mutation_pairs.isin(transitions)).astype(int)
    df["is_transversion"] = (is_snp & (~mutation_pairs.isin(transitions))).astype(int)

    # For single-record inference, chromosome aggregate features are neutralized.
    df["chrom_freq_mean"] = df["ALT_FREQ"].astype(float)
    df["chrom_rare_rate"] = df["rare_variant"].astype(float)

    for col, default in NUMERIC_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

    for col, default in CATEGORICAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].astype(str).fillna(default)

    for col in ["CHROM","REF_Base","ALT_Base","mutation_type"]:
        df[col] = df[col].astype("category")

    return df[ORDERED_FEATURES]

# ==========================================
# 🧬 HEADER
# ==========================================
st.markdown('<div class="title">🧬 GenoPredict</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Genomic Variant AI Classification</div>', unsafe_allow_html=True)

model = load_model()

# ==========================================
# 🔎 SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("## 🔎 Variant Search")

    with st.form("search"):
        chrom = st.selectbox("Chromosome", list(CHR_LENGTHS.keys()))
        pos = st.text_input("Position", "209271")
        ref = st.text_input("REF", "C").upper()
        alt = st.text_input("ALT", "A").upper()

        submit = st.form_submit_button("🚀 Search")

# ==========================================
# 🔍 SEARCH
# ==========================================
if submit:
    with st.spinner("Fetching data..."):
        df = fetch_features_from_s3(chrom, pos, ref, alt)

        if df is not None and not df.empty:
            st.session_state.target_variant_df = df.head(1)
            st.session_state.ui_state = "predict"
        else:
            st.session_state.ui_state = "manual"

# ==========================================
# ✍️ MANUAL INPUT
# ==========================================
if st.session_state.ui_state == "manual":
    st.markdown("### ✍️ Manual Input")

    with st.form("manual"):
        c1, c2, c3, c4 = st.columns(4)

        sift = c1.number_input("SIFT", 0.0, 1.0, 0.05)
        poly = c2.number_input("PolyPhen", 0.0, 1.0, 0.8)
        cadd = c3.number_input("CADD", 0.0, 60.0, 25.0)
        af = c4.number_input("AF", 0.0, 1.0, 0.0001)

        if st.form_submit_button("Predict"):
            st.session_state.target_variant_df = pd.DataFrame([{
                "#chr":chrom,"pos(1-based)":pos,"ref":ref,"alt":alt,
                "SIFT_score":sift,"Polyphen2_HVAR_score":poly,
                "CADD_phred":cadd,"gnomAD_exomes_AF":af
            }])
            st.session_state.ui_state = "predict"

# ==========================================
# 🤖 PREDICTION
# ==========================================
if st.session_state.ui_state == "predict":

    st.markdown("### 🤖 Prediction")

    if model is None:
        st.error("Model not loaded")
    else:
        try:
            X = preprocess_features(st.session_state.target_variant_df)
            pred = float(model.predict(X)[0])

            label = "PATHOGENIC" if pred > 0.5 else "BENIGN"
            color = "#dc2626" if pred > 0.5 else "#16a34a"

            st.markdown(f"""
            <div class="result-box" style="background:{color}; color:white;">
                {label}
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### 📊 Features")

            c1,c2,c3,c4 = st.columns(4)

            c1.markdown(f'<div class="metric-card">CADD<br><b>{X["CADD"].iloc[0]:.2f}</b></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="metric-card">AF<br><b>{X["ALT_FREQ"].iloc[0]:.6f}</b></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="metric-card">Mutation<br><b>{X["mutation_type"].iloc[0]}</b></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="metric-card">Impact<br><b>{X["Impact_Score"].iloc[0]:.2f}</b></div>', unsafe_allow_html=True)

            with st.expander("🔬 View Features"):
                st.dataframe(X)

        except Exception as e:
            st.error(str(e))
