"""
Rhythm OS — merge_signals (V3.5 Antifragile, HST-Compatible)

Canonical inputs:
    • natural_rhythm.csv  -> data/natural/
    • market_rhythm.csv   -> data/market/

Produces:
    • data/merged/merged_signal.csv

Guarantees:
    • One row per calendar day across entire natural range
    • Market forward-filled across weekends/holidays
    • Amplitude computed from multi-driver world motion (SP500, VIX, TempAvg, MoonIllum)
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import os

# NEW — config-driven paths
from rhythm_os.utils.config import get_path

# ---------------------------------------------------------
# Config paths
# ---------------------------------------------------------
NAT_PATH = os.path.join(get_path("paths.data"), "natural", "natural_rhythm.csv")
MKT_PATH = os.path.join(get_path("paths.data"), "market", "market_rhythm.csv")
MERGED_DIR = os.path.join(get_path("paths.data"), "merged")
MERGED_PATH = os.path.join(MERGED_DIR, "merged_signal.csv")

# ---------------------------------------------------------
# Load natural series
# ---------------------------------------------------------
def _load_natural() -> pd.DataFrame:
    if not os.path.exists(NAT_PATH):
        raise FileNotFoundError(f"Missing natural file: {NAT_PATH}")

    nat = pd.read_csv(NAT_PATH)

    if "Date" not in nat.columns:
        raise ValueError("natural_rhythm.csv missing 'Date' column")

    nat["Date"] = pd.to_datetime(nat["Date"], errors="coerce").dt.normalize()
    nat = nat.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    if nat.empty:
        raise RuntimeError("natural_rhythm.csv contains no valid rows")

    return nat


# ---------------------------------------------------------
# Load market series
# ---------------------------------------------------------
def _load_market() -> pd.DataFrame:
    if not os.path.exists(MKT_PATH):
        raise FileNotFoundError(f"Missing market file: {MKT_PATH}")

    mkt = pd.read_csv(MKT_PATH)

    if "Date" not in mkt.columns:
        raise ValueError("market_rhythm.csv missing 'Date'")

    # Normalize date
    mkt["Date"] = pd.to_datetime(mkt["Date"], errors="coerce").dt.normalize()
    mkt = mkt.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Column compatibility
    if "SP500_Close" in mkt.columns:
        mkt.rename(columns={"SP500_Close": "SP500Close"}, inplace=True)
    if "VIX_Close" in mkt.columns:
        mkt.rename(columns={"VIX_Close": "VIXClose"}, inplace=True)

    if "SP500Close" not in mkt.columns or "VIXClose" not in mkt.columns:
        raise ValueError("Market file missing SP500Close or VIXClose")

    return mkt


# ---------------------------------------------------------
# Reindex with forward-fill
# ---------------------------------------------------------
def _reindex_daily(df: pd.DataFrame, start, end, columns):
    df = df.set_index("Date").sort_index()
    full = pd.date_range(start, end, freq="D")
    df = df.reindex(full)

    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].ffill().bfill()

    df = df.reset_index().rename(columns={"index": "Date"})
    return df


# ---------------------------------------------------------
# merge_signals()
# ---------------------------------------------------------
def merge_signals() -> str:
    print("📡 [merge] Merging natural + market signals (V3.5 Antifragile)...")

    Path(MERGED_DIR).mkdir(parents=True, exist_ok=True)

    nat = _load_natural()
    mkt = _load_market()

    start = nat["Date"].min()
    end = nat["Date"].max()

    # Market reindexed onto natural horizon
    mkt_daily = _reindex_daily(
        mkt,
        start=start,
        end=end,
        columns=["SP500Close", "VIXClose"],
    )

    # Outer merge — natural is canonical
    merged = pd.merge(nat, mkt_daily, on="Date", how="outer")
    merged = merged.drop_duplicates(subset=["Date"]).sort_values("Date")
    merged.reset_index(drop=True, inplace=True)

    # -----------------------------------------------------
    # Inject AMPLITUDE:
    # -----------------------------------------------------
    from .amplitude import compute_amplitude
    merged["Amplitude"] = compute_amplitude(merged)

    # -----------------------------------------------------
    # GhostFlag enforcement
    # -----------------------------------------------------
    # If GhostFlag exists from previous pass, keep it.
    # Only create if missing (first pipeline run).
    if "GhostFlag" not in merged.columns:
        merged["GhostFlag"] = 0
    else:
        # Ensure int, but DO NOT wipe existing ghosted rows
        merged["GhostFlag"] = (
            merged["GhostFlag"]
            .fillna(0)
            .astype(int)
        )

    # Save merged_signal.csv (first-pass)
    merged.to_csv(MERGED_PATH, index=False)

    print(f"   → merged_signal.csv saved to: {MERGED_PATH}")
    print(f"   → Rows: {len(merged)}")

    return MERGED_PATH


if __name__ == "__main__":
    merge_signals()
