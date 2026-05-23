from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.features.schema_contract import CATEGORICAL_FEATURES, FEATURE_ORDER, NUMERIC_DEFAULTS



DESCRIPTIONS = {
    "CHROM": "Chromosome identifier encoded as a categorical model feature.",
    "SIFT": "SIFT deleteriousness score; lower values usually indicate stronger functional impact.",
    "PolyPhen": "PolyPhen pathogenicity score for protein-impacting variants.",
    "CADD": "CADD phred-like deleteriousness score.",
    "ALT_FREQ": "Alternative allele frequency from population data.",
    "Is_InDel": "Binary flag for insertion/deletion variants.",
    "Delta_Length": "Length difference between REF and ALT alleles.",
    "indel_size": "Absolute insertion/deletion size.",
    "Is_Frameshift": "Binary flag for indels whose length shift is not divisible by three.",
    "REF_Base": "Reference allele base encoded categorically.",
    "ALT_Base": "Alternative allele base encoded categorically.",
    "mutation_type": "REF/ALT mutation class.",
    "freq_log": "Log-transformed allele frequency feature.",
    "rare_variant": "Binary rare-variant indicator.",
    "is_ultra_rare": "Binary ultra-rare variant indicator.",
    "is_large_indel": "Binary large-indel indicator.",
    "CADD_high": "Binary indicator for high CADD score.",
    "CADD_very_high": "Binary indicator for very high CADD score.",
    "SIFT_damaging": "Binary indicator for damaging SIFT score.",
    "PolyPhen_damaging": "Binary indicator for damaging PolyPhen score.",
    "CADD_x_rare": "Interaction between CADD severity and rarity.",
    "Impact_Score": "Composite model input summarizing predicted variant impact.",
    "rare_impact": "Interaction between rarity and impact score.",
    "normalized_pos": "Position normalized within chromosome context.",
    "pos_bin": "Position bucket used by the model.",
    "pos_freq_interaction": "Interaction between genomic position and allele frequency.",
    "is_transition": "Binary single-nucleotide transition flag.",
    "is_transversion": "Binary single-nucleotide transversion flag.",
    "chrom_freq_mean": "Chromosome-level mean allele-frequency feature.",
    "chrom_rare_rate": "Chromosome-level rare-variant rate feature.",
}


def feature_type(name: str) -> str:
    return "categorical" if name in CATEGORICAL_FEATURES else "numeric"


def default_value(name: str) -> str:
    if name in NUMERIC_DEFAULTS:
        return f"`{NUMERIC_DEFAULTS[name]}`"
    if name in CATEGORICAL_FEATURES:
        return "`schema default`"
    return "`0`"


def main() -> None:
    rows = [
        "# Feature Schema",
        "",
        "This document is generated from `src/features/schema_contract.py`.",
        "The order below is the exact order enforced before model inference.",
        "",
        "| Order | Feature | Type | Default | Description |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for index, feature in enumerate(FEATURE_ORDER, start=1):
        rows.append(
            f"| {index} | `{feature}` | {feature_type(feature)} | {default_value(feature)} | "
            f"{DESCRIPTIONS.get(feature, 'Model input feature.')} |"
        )

    rows.extend(
        [
            "",
            "## Contract Rules",
            "",
            "- `enforce_feature_contract(..., fill_missing=True)` creates missing features with safe defaults.",
            "- Numeric columns are coerced with `pandas.to_numeric` and nulls are filled from the contract.",
            "- Categorical columns are cast to pandas `category` before prediction.",
            "- API and VCF batch workflows both pass through this contract before model scoring.",
        ]
    )
    (ROOT / "FEATURE_SCHEMA.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
