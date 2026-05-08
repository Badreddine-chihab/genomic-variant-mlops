import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.schema_contract import CATEGORICAL_FEATURES, FEATURE_ORDER
from src.orchestration.config_utils import ConfigManager


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


CHR_LENGTHS = {
    "1": 248956422,
    "2": 242193529,
    "3": 198295559,
    "4": 190214555,
    "5": 181538259,
    "6": 170805979,
    "7": 159345973,
    "8": 145138636,
    "9": 138394717,
    "10": 133797422,
    "11": 135086622,
    "12": 133275309,
    "13": 114364328,
    "14": 107043718,
    "15": 101991189,
    "16": 90338345,
    "17": 83257441,
    "18": 80373285,
    "19": 58617616,
    "20": 64444167,
    "21": 46709983,
    "22": 50818468,
    "X": 156040895,
    "Y": 57227415,
    "M": 16569,
}

TRANSITIONS = {"A_G", "G_A", "C_T", "T_C"}
TRANVERSIONS = {"A_C", "C_A", "A_T", "T_A", "C_G", "G_C", "G_T", "T_G"}


def _first_base(series: pd.Series, default: str = "N") -> pd.Series:
    return (
        series.fillna(default)
        .astype(str)
        .str.upper()
        .str.slice(0, 1)
        .replace({"": default})
    )


def encode_features(input_path: Path, output_path: Path) -> pd.DataFrame:
    logger.info("Loading model-ready data from %s", input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    df = pd.read_parquet(input_path)
    required = {
        "#chr",
        "pos(1-based)",
        "ref",
        "alt",
        "SIFT_score",
        "Polyphen2_HDIV_score",
        "CADD_phred",
        "gnomAD_exomes_AF",
        "target",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Model-ready dataset is missing required columns: {missing}")

    out = pd.DataFrame(index=df.index)
    out["CHROM"] = df["#chr"].astype(str).str.replace("chr", "", regex=False)
    out["SIFT"] = pd.to_numeric(df["SIFT_score"], errors="coerce").fillna(-1.0)
    out["PolyPhen"] = pd.to_numeric(df["Polyphen2_HDIV_score"], errors="coerce").fillna(-1.0)
    out["CADD"] = pd.to_numeric(df["CADD_phred"], errors="coerce").fillna(-1.0)
    out["ALT_FREQ"] = pd.to_numeric(df["gnomAD_exomes_AF"], errors="coerce").fillna(0.0)
    out["Target"] = pd.to_numeric(df["target"], errors="coerce").fillna(0).astype("int32")

    ref = df["ref"].fillna("").astype(str)
    alt = df["alt"].fillna("").astype(str)
    ref_len = ref.str.len()
    alt_len = alt.str.len()

    out["Is_InDel"] = (ref_len != alt_len).astype("int8")
    out["Delta_Length"] = (alt_len - ref_len).astype("int16")
    out["indel_size"] = out["Delta_Length"].abs().astype("int16")
    out["Is_Frameshift"] = (
        (out["Is_InDel"] == 1) & ((out["indel_size"] % 3) != 0)
    ).astype("int8")

    out["REF_Base"] = _first_base(ref)
    alt_base = _first_base(alt)
    out["ALT_Base"] = np.where(out["Is_InDel"] == 1, "-", alt_base)
    out["mutation_type"] = np.where(
        out["Is_InDel"] == 1,
        "INDEL",
        out["REF_Base"].astype(str) + "_" + out["ALT_Base"].astype(str),
    )

    out["freq_log"] = np.log1p(out["ALT_FREQ"]).astype("float32")
    out["rare_variant"] = (out["ALT_FREQ"] < 0.005).astype("int8")
    out["is_ultra_rare"] = (out["ALT_FREQ"] < 0.001).astype("int8")
    out["is_large_indel"] = (out["indel_size"] > 5).astype("int8")
    out["CADD_high"] = (out["CADD"] > 20).astype("int8")
    out["CADD_very_high"] = (out["CADD"] > 30).astype("int8")
    out["SIFT_damaging"] = ((out["SIFT"] >= 0) & (out["SIFT"] < 0.05)).astype("int8")
    out["PolyPhen_damaging"] = (out["PolyPhen"] > 0.85).astype("int8")
    out["CADD_x_rare"] = (out["CADD"] * out["rare_variant"]).astype("float32")

    out["Impact_Score"] = (
        out["Is_Frameshift"] * 3.0
        + out["is_large_indel"] * 2.0
        + out["indel_size"] * 0.1
        + out["is_ultra_rare"] * 2.0
        + out["CADD_high"] * 2.0
    ).astype("float32")
    out["rare_impact"] = (out["rare_variant"] * out["Impact_Score"]).astype("float32")

    positions = pd.to_numeric(df["pos(1-based)"], errors="coerce").fillna(0.0)
    chr_lengths = out["CHROM"].map(CHR_LENGTHS).astype("float64")
    out["normalized_pos"] = (positions / chr_lengths).replace([np.inf, -np.inf], 0).fillna(0)
    out["normalized_pos"] = out["normalized_pos"].clip(lower=0, upper=1).astype("float32")
    out["pos_bin"] = np.floor(out["normalized_pos"] * 10).clip(0, 9).astype("int8")
    out["pos_freq_interaction"] = (out["normalized_pos"] * out["ALT_FREQ"]).astype("float32")

    substitutions = out["mutation_type"].astype(str)
    out["is_transition"] = substitutions.isin(TRANSITIONS).astype("int8")
    out["is_transversion"] = substitutions.isin(TRANVERSIONS).astype("int8")

    out["chrom_freq_mean"] = (
        out.groupby("CHROM", observed=False)["ALT_FREQ"].transform("mean").fillna(0).astype("float32")
    )
    out["chrom_rare_rate"] = (
        out.groupby("CHROM", observed=False)["rare_variant"].transform("mean").fillna(0).astype("float32")
    )

    for col in ["SIFT", "PolyPhen", "CADD", "ALT_FREQ"]:
        out[col] = out[col].astype("float32")

    for col in CATEGORICAL_FEATURES:
        out[col] = out[col].astype("category")

    final = out[FEATURE_ORDER + ["Target"]]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(output_path, index=False)
    logger.info("Saved encoded training dataset to %s with shape %s", output_path, final.shape)
    return final


def main() -> None:
    cm = ConfigManager()
    input_path = cm.get_path("paths.data.model_ready")
    output_path = cm.get_path("paths.data.final_training")
    encode_features(input_path, output_path)


if __name__ == "__main__":
    main()
