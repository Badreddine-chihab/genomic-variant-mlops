from __future__ import annotations

from typing import Iterable

import pandas as pd


FEATURE_ORDER = [
    "CHROM",
    "SIFT",
    "PolyPhen",
    "CADD",
    "ALT_FREQ",
    "Is_InDel",
    "Delta_Length",
    "indel_size",
    "Is_Frameshift",
    "REF_Base",
    "ALT_Base",
    "mutation_type",
    "freq_log",
    "rare_variant",
    "is_ultra_rare",
    "is_large_indel",
    "CADD_high",
    "CADD_very_high",
    "SIFT_damaging",
    "PolyPhen_damaging",
    "CADD_x_rare",
    "Impact_Score",
    "rare_impact",
    "normalized_pos",
    "pos_bin",
    "pos_freq_interaction",
    "is_transition",
    "is_transversion",
    "chrom_freq_mean",
    "chrom_rare_rate",
]

CATEGORICAL_FEATURES = ["CHROM", "REF_Base", "ALT_Base", "mutation_type"]

NUMERIC_DEFAULTS = {
    "SIFT": -1.0,
    "PolyPhen": -1.0,
    "CADD": -1.0,
    "ALT_FREQ": 0.0,
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
    "CHROM": "1",
    "REF_Base": "N",
    "ALT_Base": "N",
    "mutation_type": "N_N",
}


def _missing(columns: Iterable[str], required: Iterable[str]) -> list[str]:
    col_set = set(columns)
    return [c for c in required if c not in col_set]


def enforce_feature_contract(df: pd.DataFrame, fill_missing: bool = False) -> pd.DataFrame:
    """
    Enforce model feature schema with stable column order.
    When fill_missing=True, required columns are created with contract defaults.
    """
    out = df.copy()
    missing = _missing(out.columns, FEATURE_ORDER)

    if missing and not fill_missing:
        raise ValueError(f"Missing required model features: {missing}")

    if fill_missing:
        for col in missing:
            if col in NUMERIC_DEFAULTS:
                out[col] = NUMERIC_DEFAULTS[col]
            elif col in CATEGORICAL_DEFAULTS:
                out[col] = CATEGORICAL_DEFAULTS[col]
            else:
                out[col] = 0

    for col in NUMERIC_DEFAULTS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(NUMERIC_DEFAULTS[col])

    for col, default in CATEGORICAL_DEFAULTS.items():
        if col in out.columns:
            out[col] = out[col].astype(str).fillna(default)

    for col in CATEGORICAL_FEATURES:
        if col in out.columns:
            out[col] = out[col].astype("category")

    return out[FEATURE_ORDER]
