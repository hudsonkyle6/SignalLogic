"""
Rhythm OS Loader — V3.2 (Config + GhostFlag Integrated)
"""
ARCHIVED — Jan 2026

This module implemented the full data loading,
schema enforcement, smoothing, and feature
engineering pipeline for the pre-sovereign
Rhythm OS.

Retired when the Core was sealed as a
pure observational kernel emitting immutable Waves.
"""


Responsibilities:
  - Load canonical merged_signal.csv
  - Enforce schema, gently smooth, compute rolling features
  - Guarantee GhostFlag column integrity
  - Use config.yaml for all paths
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import os

from rhythm_os.core.resonance.smoothing import natural_smooth
from rhythm_os.utils.config import get_path


# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------
MERGED_DIR = get_path("paths.merged")
MERGED_PATH = os.path.join(MERGED_DIR, "merged_signal.csv")


# ---------------------------------------------------------------------------
# V1: Basic Loaders
# ---------------------------------------------------------------------------

def load_merged_signal() -> pd.DataFrame:
    """Load the full merged_signal.csv from config path."""
    if not os.path.exists(MERGED_PATH):
        raise FileNotFoundError(f"merged_signal.csv not found at {MERGED_PATH}")
    df = pd.read_csv(MERGED_PATH)

    # GhostFlag: guarantee existence + correct type
    if "GhostFlag" not in df.columns:
        df["GhostFlag"] = 0
    df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    return df


def load_latest_snapshot() -> pd.DataFrame:
    """Load the most recent daily_* snapshot from data/merged."""
    merged_dir = Path(MERGED_DIR)

    if not merged_dir.exists():
        raise FileNotFoundError(f"No merged directory at {MERGED_DIR}")

    snapshots = sorted(merged_dir.glob("daily_*.csv"))
    if not snapshots:
        raise FileNotFoundError(f"No daily_* snapshots in {MERGED_DIR}")

    df = pd.read_csv(snapshots[-1])

    if "GhostFlag" not in df.columns:
        df["GhostFlag"] = 0
    df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    return df


# ---------------------------------------------------------------------------
# V2: Smoothed + Schema-Enforced Loader
# ---------------------------------------------------------------------------

REQUIRED_BASE_COLS = ["Date"]

OPTIONAL_SIGNAL_COLS = [
    "Season", "SignalState", "ResonanceValue",
    "Amplitude", "amp"
]

OPTIONAL_MARKET_COLS = ["SP500Close", "VIXClose"]

OPTIONAL_NAT_COLS = ["TempAvg", "MoonIllum"]

OPTIONAL_COUPLING_COLS = ["CouplingCol", "CouplingLag", "CouplingPearson"]

# NEW: GhostFlag is a mandatory column throughout the system
MANDATORY_FLAGS = ["GhostFlag"]


def load_smoothed_merged_signal() -> pd.DataFrame:
    raw = load_merged_signal()
    df = _enforce_schema(raw)
    df = _fill_missing_dates(df)
    df = _smooth_signals(df)
    df = _tag_seasons(df)
    df = _compute_rolling_features(df)

    # Final GhostFlag enforcement
    if "GhostFlag" in df.columns:
        df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    return df


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the DataFrame has:
      - a proper Date column (datetime, sorted)
      - placeholders for missing canonical columns
      - a clean GhostFlag column
    """
    df = df.copy()

    if "Date" not in df.columns:
        raise ValueError("Expected a 'Date' column in merged_signal.csv")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Add missing canonical columns
    all_cols = (
        REQUIRED_BASE_COLS
        + OPTIONAL_SIGNAL_COLS
        + OPTIONAL_MARKET_COLS
        + OPTIONAL_NAT_COLS
        + OPTIONAL_COUPLING_COLS
    )

    for col in all_cols:
        if col not in df.columns:
            df[col] = np.nan

    # GhostFlag is mandatory
    if "GhostFlag" not in df.columns:
        df["GhostFlag"] = 0

    df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    # Legacy compatibility
    if "Amplitude" in df.columns and "amp" in df.columns:
        mask = df["Amplitude"].isna() & df["amp"].notna()
        df.loc[mask, "Amplitude"] = df.loc[mask, "amp"]

    if "SP500_Close" in df.columns and "SP500Close" in df.columns:
        mask = df["SP500Close"].isna() & df["SP500_Close"].notna()
        df.loc[mask, "SP500Close"] = df.loc[mask, "SP500_Close"]

    if "VIX_Close" in df.columns and "VIXClose" in df.columns:
        mask = df["VIXClose"].isna() & df["VIX_Close"].notna()
        df.loc[mask, "VIXClose"] = df.loc[mask, "VIX_Close"]

    return df


def _fill_missing_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex to continuous daily date range, preserving GhostFlag."""
    df = df.copy().sort_values("Date").reset_index(drop=True)
    if df.empty:
        return df

    # Remove duplicate dates BEFORE reindex
    if df["Date"].duplicated().any():
        df = df.drop_duplicates(subset=["Date"], keep="last")

    full_index = pd.date_range(df["Date"].min(), df["Date"].max(), freq="D")

    df = df.set_index("Date").reindex(full_index)

    # Preserve/restore GhostFlag after reindex
    if "GhostFlag" in df.columns:
        df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    df.index.name = "Date"
    df = df.reset_index()

    return df


def _smooth_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # NEVER smooth GhostFlag
    if "GhostFlag" in df.columns:
        df["GhostFlag"] = df["GhostFlag"].astype(int)

    # Market smoother
    for col in ("SP500Close", "VIXClose"):
        if col in df.columns:
            df[col] = natural_smooth(df[col])

    # Natural smoother
    for col in ("TempAvg", "MoonIllum"):
        if col in df.columns:
            df[col] = natural_smooth(df[col])

    # Amplitude / Resonance smoother
    for col in ("Amplitude", "ResonanceValue"):
        if col in df.columns:
            df[col] = natural_smooth(df[col])

    return df


def _tag_seasons(df: pd.DataFrame) -> pd.DataFrame:
    """Assign seasonal archetypes."""
    df = df.copy()

    def _season_for_date(d: pd.Timestamp) -> str:
        m = d.month
        if m in (3, 4, 5):
            return "Build"
        if m in (6, 7, 8):
            return "Fuel"
        if m in (9, 10, 11):
            return "Tend"
        return "Reflect"

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Season"] = df["Date"].apply(_season_for_date)

    return df


def _compute_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling means and 7-day resonance slope."""
    df = df.copy().sort_values("Date").reset_index(drop=True)

    # Rolling means for resonance
    if "ResonanceValue" in df.columns:
        df["Res_3d_mean"] = df["ResonanceValue"].rolling(3, min_periods=1).mean()
        df["Res_7d_mean"] = df["ResonanceValue"].rolling(7, min_periods=1).mean()
    else:
        df["Res_3d_mean"] = np.nan
        df["Res_7d_mean"] = np.nan

    # Rolling means for amplitude
    amp_col = "Amplitude" if "Amplitude" in df.columns else "amp" if "amp" in df.columns else None
    if amp_col:
        df["Amp_3d_mean"] = df[amp_col].rolling(3, min_periods=1).mean()
        df["Amp_7d_mean"] = df[amp_col].rolling(7, min_periods=1).mean()
    else:
        df["Amp_3d_mean"] = np.nan
        df["Amp_7d_mean"] = np.nan

    # Resonance 7-day slope
    if "ResonanceValue" in df.columns:
        res = df["ResonanceValue"].to_numpy(float)
        slopes = np.full_like(res, np.nan, float)

        for idx in range(len(res)):
            start = max(0, idx - 6)
            segment = res[start:idx + 1]
            if len(segment) >= 3 and not np.isnan(segment).all():
                x = np.arange(len(segment), dtype=float)
                s, _ = np.polyfit(x, segment, 1)
                slopes[idx] = s

        df["Res_7d_slope"] = slopes
    else:
        df["Res_7d_slope"] = np.nan

    return df
