# rhythm_os/core/sources/market_shield.py
"""
Market Ingestion Shield (MIS v1) — Silent

Purpose:
    Harden S&P 500 (^GSPC) and VIX (^VIX) ingestion so that:
      • No NaNs propagate into SP500Close / VIXClose
      • Columns are always present
      • Fallback tiers protect against Yahoo / network quirks

Rules:
    • NO print()
    • NO human-facing output
    • Raise on failure where appropriate
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf


# --------------------------------------------------------------
# Paths
# --------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]    # -> SignalLogic
DATA_ROOT = ROOT / "data"
MARKET_DIR = DATA_ROOT / "market"

MARKET_FILE = MARKET_DIR / "market_rhythm.csv"
SHIELD_FILE = MARKET_DIR / "market_shield.csv"


SYMBOLS = ["^GSPC", "^VIX"]
COL_MAP = {
    "^GSPC": "SP500Close",
    "^VIX": "VIXClose",
}


# --------------------------------------------------------------
# Helpers (Silent)
# --------------------------------------------------------------

def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Date" not in df.columns:
        return df
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def _validate_multi_df(df: pd.DataFrame, symbols: List[str]) -> bool:
    """Check that the multi-ticker download has Close and all symbols present."""
    if df is None or df.empty:
        return False
    if "Close" not in df.columns:
        return False
    try:
        closes = df["Close"]
    except Exception:
        return False
    for sym in symbols:
        if sym not in closes.columns:
            return False
    return True


def _multi_download_window(days: int) -> Tuple[Optional[pd.DataFrame], str]:
    """Tier 1: Multi-symbol download over requested window."""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    df = yf.download(SYMBOLS, start=start_date, end=end_date, progress=False)

    if _validate_multi_df(df, SYMBOLS):
        close_df = df["Close"].reset_index()
        return close_df, "tier1_multi"
    return None, "tier1_multi_fail"


def _multi_download_14d() -> Tuple[Optional[pd.DataFrame], str]:
    """Tier 2: Try last ~14 days multi-symbol to get at least recent data."""
    df = yf.download(SYMBOLS, period="14d", progress=False)

    if _validate_multi_df(df, SYMBOLS):
        close_df = df["Close"].reset_index()
        return close_df, "tier2_multi_14d"
    return None, "tier2_multi_14d_fail"


def _single_symbol_download(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Download a single symbol, return Date + mapped Close column, or None."""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    df = yf.download(symbol, start=start_date, end=end_date, progress=False)
    if df is None or df.empty or "Close" not in df.columns:
        return None

    out = df[["Close"]].reset_index().rename(columns={"Close": COL_MAP[symbol]})
    return out


def _tier3_single_symbol_merge(days: int) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Tier 3:
        Try downloading ^GSPC and ^VIX separately, then merge on Date.
    """
    gspc_df = _single_symbol_download("^GSPC", days)
    vix_df = _single_symbol_download("^VIX", days)

    if gspc_df is None and vix_df is None:
        return None, "tier3_single_fail"

    if gspc_df is not None and vix_df is not None:
        merged = pd.merge(gspc_df, vix_df, on="Date", how="outer")
    elif gspc_df is not None:
        merged = gspc_df.copy()
        merged["VIXClose"] = pd.NA
    else:
        merged = vix_df.copy()
        merged["SP500Close"] = pd.NA

    merged = _normalize_dates(merged)
    return merged, "tier3_single_merge"


def _tier4_historical_fallback() -> Tuple[pd.DataFrame, str]:
    """
    Tier 4:
        Historical fallback from existing market_rhythm.csv.

        If MARKET_FILE exists:
            • Take last non-NaN row
            • Repeat its values for "today" (single row)
        Else:
            • Create a one-row DataFrame with 0-valued SP500Close/VIXClose
    """
    today = datetime.today().date()

    if MARKET_FILE.exists():
        hist = pd.read_csv(MARKET_FILE)
        hist = _normalize_dates(hist)
        if not hist.empty:
            last_row = hist.iloc[-1].copy()
            last_sp = pd.to_numeric(last_row.get("SP500Close", 0.0), errors="coerce")
            last_vx = pd.to_numeric(last_row.get("VIXClose", 0.0), errors="coerce")

            if pd.isna(last_sp):
                last_sp = 0.0
            if pd.isna(last_vx):
                last_vx = 0.0

            df = pd.DataFrame([{
                "Date": pd.Timestamp(today),
                "SP500Close": float(last_sp),
                "VIXClose": float(last_vx),
            }])
            return df, "tier4_hist_copy"

    df = pd.DataFrame([{
        "Date": pd.Timestamp(today),
        "SP500Close": 0.0,
        "VIXClose": 0.0,
    }])
    return df, "tier4_synthetic"


def _clean_nans_and_sort(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Final cleaning:
        • Normalize Date
        • Forward-fill / back-fill SP500Close, VIXClose
        • Count NaNs corrected
    """
    df = _normalize_dates(df)

    if "SP500Close" not in df.columns:
        df["SP500Close"] = pd.NA
    if "VIXClose" not in df.columns:
        df["VIXClose"] = pd.NA

    df["SP500Close"] = pd.to_numeric(df["SP500Close"], errors="coerce")
    df["VIXClose"] = pd.to_numeric(df["VIXClose"], errors="coerce")

    before_nans = int(df[["SP500Close", "VIXClose"]].isna().sum().sum())

    df[["SP500Close", "VIXClose"]] = df[["SP500Close", "VIXClose"]].ffill().bfill()

    after_nans = int(df[["SP500Close", "VIXClose"]].isna().sum().sum())
    corrected = before_nans - after_nans

    if after_nans > 0:
        df["SP500Close"] = df["SP500Close"].fillna(0.0)
        df["VIXClose"] = df["VIXClose"].fillna(0.0)

    return df, max(corrected, 0)


# --------------------------------------------------------------
# Public API
# --------------------------------------------------------------

def run_market_shield(days: int = 365, write_files: bool = True) -> pd.DataFrame:
    """
    Main entrypoint for Market Ingestion Shield v1 (Silent).

    Returns:
        Cleaned DataFrame with columns: Date, SP500Close, VIXClose
    """
    MARKET_DIR.mkdir(parents=True, exist_ok=True)

    close_df: Optional[pd.DataFrame] = None

    close_df, _ = _multi_download_window(days)
    if close_df is None:
        close_df, _ = _multi_download_14d()
    if close_df is None:
        close_df, _ = _tier3_single_symbol_merge(days)
    if close_df is None:
        close_df, _ = _tier4_historical_fallback()

    close_df = _normalize_dates(close_df)

    # If we came from multi-ticker Close, rename columns
    if "^GSPC" in close_df.columns or "^VIX" in close_df.columns:
        rename_map = {}
        if "^GSPC" in close_df.columns:
            rename_map["^GSPC"] = "SP500Close"
        if "^VIX" in close_df.columns:
            rename_map["^VIX"] = "VIXClose"
        close_df = close_df.rename(columns=rename_map)

    if "SP500Close" not in close_df.columns:
        close_df["SP500Close"] = pd.NA
    if "VIXClose" not in close_df.columns:
        close_df["VIXClose"] = pd.NA

    clean_df, _ = _clean_nans_and_sort(close_df)

    if write_files:
        clean_df.to_csv(SHIELD_FILE, index=False)
        clean_df.to_csv(MARKET_FILE, index=False)

    return clean_df


if __name__ == "__main__":
    # Core stays silent even when invoked as a module.
    run_market_shield(days=365, write_files=True)

