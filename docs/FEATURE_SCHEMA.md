# Feature Schema

This document is generated from `src/features/schema_contract.py`.
The order below is the exact order enforced before model inference.

| Order | Feature | Type | Default | Description |
| ---: | --- | --- | --- | --- |
| 1 | `CHROM` | categorical | `schema default` | Chromosome identifier encoded as a categorical model feature. |
| 2 | `SIFT` | numeric | `-1.0` | SIFT deleteriousness score; lower values usually indicate stronger functional impact. |
| 3 | `PolyPhen` | numeric | `-1.0` | PolyPhen pathogenicity score for protein-impacting variants. |
| 4 | `CADD` | numeric | `-1.0` | CADD phred-like deleteriousness score. |
| 5 | `ALT_FREQ` | numeric | `0.0` | Alternative allele frequency from population data. |
| 6 | `Is_InDel` | numeric | `0` | Binary flag for insertion/deletion variants. |
| 7 | `Delta_Length` | numeric | `0` | Length difference between REF and ALT alleles. |
| 8 | `indel_size` | numeric | `0` | Absolute insertion/deletion size. |
| 9 | `Is_Frameshift` | numeric | `0` | Binary flag for indels whose length shift is not divisible by three. |
| 10 | `REF_Base` | categorical | `schema default` | Reference allele base encoded categorically. |
| 11 | `ALT_Base` | categorical | `schema default` | Alternative allele base encoded categorically. |
| 12 | `mutation_type` | categorical | `schema default` | REF/ALT mutation class. |
| 13 | `freq_log` | numeric | `0.0` | Log-transformed allele frequency feature. |
| 14 | `rare_variant` | numeric | `0` | Binary rare-variant indicator. |
| 15 | `is_ultra_rare` | numeric | `0` | Binary ultra-rare variant indicator. |
| 16 | `is_large_indel` | numeric | `0` | Binary large-indel indicator. |
| 17 | `CADD_high` | numeric | `0` | Binary indicator for high CADD score. |
| 18 | `CADD_very_high` | numeric | `0` | Binary indicator for very high CADD score. |
| 19 | `SIFT_damaging` | numeric | `0` | Binary indicator for damaging SIFT score. |
| 20 | `PolyPhen_damaging` | numeric | `0` | Binary indicator for damaging PolyPhen score. |
| 21 | `CADD_x_rare` | numeric | `0.0` | Interaction between CADD severity and rarity. |
| 22 | `Impact_Score` | numeric | `0.0` | Composite model input summarizing predicted variant impact. |
| 23 | `rare_impact` | numeric | `0.0` | Interaction between rarity and impact score. |
| 24 | `normalized_pos` | numeric | `0.0` | Position normalized within chromosome context. |
| 25 | `pos_bin` | numeric | `0` | Position bucket used by the model. |
| 26 | `pos_freq_interaction` | numeric | `0.0` | Interaction between genomic position and allele frequency. |
| 27 | `is_transition` | numeric | `0` | Binary single-nucleotide transition flag. |
| 28 | `is_transversion` | numeric | `0` | Binary single-nucleotide transversion flag. |
| 29 | `chrom_freq_mean` | numeric | `0.0` | Chromosome-level mean allele-frequency feature. |
| 30 | `chrom_rare_rate` | numeric | `0.0` | Chromosome-level rare-variant rate feature. |

## Contract Rules

- `enforce_feature_contract(..., fill_missing=True)` creates missing features with safe defaults.
- Numeric columns are coerced with `pandas.to_numeric` and nulls are filled from the contract.
- Categorical columns are cast to pandas `category` before prediction.
- API and VCF batch workflows both pass through this contract before model scoring.
