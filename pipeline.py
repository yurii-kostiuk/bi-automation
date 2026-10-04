"""Retail pipeline: load -> validate -> clean -> KPIs -> anomalies -> export.

Run locally:  python pipeline.py
In production it is started on a schedule by GitHub Actions.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
RAW_FILE = Path("data/online_retail_II.csv.gz")
OUTPUT_DIR = Path("data")
COL_INVOICE = "Invoice"
COL_DATE = "InvoiceDate"
COL_QUANTITY = "Quantity"
COL_PRICE = "Price"
COL_CUSTOMER = "Customer ID"
Z_SCORE_THRESHOLD = 5
# -----------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("pipeline")

REQUIRED_COLUMNS = [COL_INVOICE, COL_DATE, COL_QUANTITY, COL_PRICE, COL_CUSTOMER]
FLAG_COLUMNS = ["is_duplicate", "is_bad_price", "is_bad_quantity", "is_outlier"]


def load_data(path):
    log.info("Loading %s", path)
    df = pd.read_csv(path)
    log.info("Loaded %d rows, %d columns", *df.shape)
    return df


def validate_columns(df):
    """Stop early with a clear message if the file structure is unexpected."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def add_columns(df):
    df = df.copy()
    df[COL_DATE] = pd.to_datetime(df[COL_DATE])
    df["Revenue"] = df[COL_QUANTITY] * df[COL_PRICE]
    # Invoices starting with "C" are cancellations (returns)
    df["IsReturn"] = df[COL_INVOICE].astype(str).str.startswith("C")
    return df


def build_monthly_kpi(df):
    monthly = (
        df.groupby(df[COL_DATE].dt.to_period("M"))
        .agg(
            revenue=("Revenue", "sum"),
            orders=(COL_INVOICE, "nunique"),
            customers=(COL_CUSTOMER, "nunique"),
        )
        .reset_index()
        .rename(columns={COL_DATE: "month"})
    )
    monthly["month"] = monthly["month"].astype(str)
    return monthly


def flag_anomalies(df):
    flagged = df.copy()

    # Rule 1: exact duplicate rows (first occurrence is kept, the rest are flagged)
    flagged["is_duplicate"] = df.duplicated(keep="first")
    # Rule 2: zero or negative unit price
    flagged["is_bad_price"] = df[COL_PRICE] <= 0
    # Rule 3: zero or negative quantity that is not a return
    flagged["is_bad_quantity"] = (df[COL_QUANTITY] <= 0) & ~df["IsReturn"]

    # Rule 4: unusually large sales (z-score), calculated on normal sales only
    sales = df[~df["IsReturn"] & (df[COL_PRICE] > 0) & (df[COL_QUANTITY] > 0)]
    z_scores = (sales["Revenue"] - sales["Revenue"].mean()) / sales["Revenue"].std()
    flagged["is_outlier"] = False
    flagged.loc[z_scores[z_scores.abs() > Z_SCORE_THRESHOLD].index, "is_outlier"] = True

    flagged["any_flag"] = flagged[FLAG_COLUMNS].any(axis=1)
    return flagged


def summarize_flags(flagged):
    summary = flagged[FLAG_COLUMNS].sum().rename("rows").to_frame()
    summary["share_pct"] = (summary["rows"] / len(flagged) * 100).round(2)
    return summary.reset_index().rename(columns={"index": "rule"})


def main():
    df = load_data(RAW_FILE)
    validate_columns(df)
    df = add_columns(df)

    monthly = build_monthly_kpi(df)
    flagged = flag_anomalies(df)
    summary = summarize_flags(flagged)

    OUTPUT_DIR.mkdir(exist_ok=True)
    monthly.to_csv(OUTPUT_DIR / "monthly_kpi.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "anomaly_summary.csv", index=False)
    flagged[flagged["any_flag"]].to_csv(OUTPUT_DIR / "anomalies.csv", index=False)

    # One-row log of this run (used for the data quality page and to show the run happened)
    run_summary = pd.DataFrame(
        [
            {
                "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "rows_loaded": len(df),
                "rows_flagged": int(flagged["any_flag"].sum()),
                "date_from": df[COL_DATE].min(),
                "date_to": df[COL_DATE].max(),
            }
        ]
    )
    run_summary.to_csv(OUTPUT_DIR / "run_summary.csv", index=False)

    log.info("Done. Flagged %d of %d rows", flagged["any_flag"].sum(), len(df))


if __name__ == "__main__":
    main()
