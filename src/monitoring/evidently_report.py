import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.monitoring.prediction_logger import events_to_dataframe


REFERENCE_DEFAULT = Path("data/processed/final_training_dataset.parquet")
REPORT_DEFAULT = Path("reports/monitoring/latest_drift_report.html")
FEATURE_COLUMNS = ["CADD", "SIFT", "PolyPhen", "ALT_FREQ"]


def _normalize_current_events(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "cadd": "CADD",
        "sift": "SIFT",
        "polyphen": "PolyPhen",
        "alt_freq": "ALT_FREQ",
        "prediction": "prediction",
        "chrom": "CHROM",
    }
    normalized = df.rename(columns=rename_map).copy()
    for col in FEATURE_COLUMNS + ["prediction"]:
        if col in normalized:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")
    return normalized


def _select_common_columns(reference: pd.DataFrame, current: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates: Iterable[str] = FEATURE_COLUMNS + ["prediction", "CHROM", "mutation_type"]
    columns = [col for col in candidates if col in reference.columns and col in current.columns]
    if not columns:
        columns = [col for col in FEATURE_COLUMNS if col in current.columns]
        reference = reference.reindex(columns=columns)
    return reference[columns].dropna(how="all"), current[columns].dropna(how="all")


def _fallback_html(reference: pd.DataFrame, current: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for col in FEATURE_COLUMNS:
        if col not in current.columns:
            continue
        current_series = pd.to_numeric(current[col], errors="coerce").dropna()
        reference_series = pd.to_numeric(reference[col], errors="coerce").dropna() if col in reference else pd.Series(dtype=float)
        rows.append(
            {
                "feature": col,
                "reference_mean": reference_series.mean() if not reference_series.empty else None,
                "current_mean": current_series.mean() if not current_series.empty else None,
                "reference_missing_rate": reference[col].isna().mean() if col in reference else None,
                "current_missing_rate": current[col].isna().mean() if col in current else None,
            }
        )

    summary = pd.DataFrame(rows)
    html = f"""
    <html>
      <head>
        <title>GenoPredict Drift Report</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 32px; color: #172033; }}
          table {{ border-collapse: collapse; width: 100%; }}
          th, td {{ border: 1px solid #d8dee9; padding: 8px; text-align: left; }}
          th {{ background: #eef2f7; }}
        </style>
      </head>
      <body>
        <h1>GenoPredict Drift Report</h1>
        <p>Evidently was not available, so this fallback report shows simple feature summary checks.</p>
        <p>Reference rows: {len(reference)} | Current rows: {len(current)}</p>
        {summary.to_html(index=False)}
      </body>
    </html>
    """
    output_path.write_text(html, encoding="utf-8")


def generate_report(reference_path: Path, output_path: Path) -> Path:
    current = _normalize_current_events(events_to_dataframe())
    if current.empty:
        raise RuntimeError("No prediction monitoring events found. Run predictions before generating a drift report.")

    reference = pd.read_parquet(reference_path)
    reference, current = _select_common_columns(reference, current)

    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset, DataSummaryPreset

        report = Report(metrics=[DataSummaryPreset(), DataDriftPreset()])
        report.run(reference_data=reference, current_data=current)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.save_html(str(output_path))
    except Exception:
        _fallback_html(reference, current, output_path)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a GenoPredict data drift report.")
    parser.add_argument("--reference", type=Path, default=REFERENCE_DEFAULT)
    parser.add_argument("--output", type=Path, default=REPORT_DEFAULT)
    args = parser.parse_args()

    output_path = generate_report(args.reference, args.output)
    print(f"Drift report written to {output_path}")


if __name__ == "__main__":
    main()
