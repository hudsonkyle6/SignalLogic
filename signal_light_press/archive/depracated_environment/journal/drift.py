"""
Journal Engine — drift.py
Computes HST drift metrics for the entire journal.

Outputs written back into:
    data/journal/signal_journal.csv

This file assumes the journal was already rebuilt by:
    rebuild.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
JOURNAL = DATA / "journal" / "signal_journal.csv"


# ---------------------------------------------------------
# Angular distance helper
# ---------------------------------------------------------
def angular_difference(a: float, b: float) -> float:
    """
    Computes wrapped angular distance between a and b.
    Output in radians, centered on 0.
    """
    if pd.isna(a) or pd.isna(b):
        return np.nan
    diff = a - b
    # Wrap into [-pi, pi]
    diff = (diff + np.pi) % (2 * np.pi) - np.pi
    return diff


# ---------------------------------------------------------
# Rolling correlation helper
# ---------------------------------------------------------
def safe_corr(series_a: pd.Series, series_b: pd.Series, window: int = 7):
    """
    Safe rolling correlation:
      - returns NaN until enough rows exist
      - returns NaN if all values are constant or missing
    """
    return (
        series_a
        .rolling(window)
        .corr(series_b)
    )


# ---------------------------------------------------------
# Drift Calculator
# ---------------------------------------------------------
def compute_drift():
    print("📘 Computing HST drift metrics...")

    if not JOURNAL.exists():
        raise FileNotFoundError(f"Cannot find journal at: {JOURNAL}")

    df = pd.read_csv(JOURNAL)

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # --------------------------
    # HSTResDrift
    # --------------------------
    df["HSTResDrift"] = df["H_t"].diff()

    # --------------------------
    # HSTAmpCorr (Amplitude ↔ H_t)
    # --------------------------
    df["HSTAmpCorr"] = safe_corr(df["Amplitude"] if "Amplitude" in df else df["ResonanceValue"], 
                                 df["H_t"], window=7)

    # --------------------------
    # HSTTempCorr (TempAvg ↔ H_t)
    # --------------------------
    df["HSTTempCorr"] = safe_corr(df["TempAvg"], df["H_t"], window=7)

    # --------------------------
    # HSTPhaseDiv (φ_h ↔ φ_e angular distance)
    # --------------------------
    df["phi_h"] = pd.to_numeric(df["phi_h"], errors="coerce")
    df["phi_e"] = pd.to_numeric(df["phi_e"], errors="coerce")

    df["HSTPhaseDiv"] = [
        angular_difference(a, b)
        for a, b in zip(df["phi_h"], df["phi_e"])
    ]

    # --------------------------
    # Save journal
    # --------------------------
    df.to_csv(JOURNAL, index=False)

    print("✅ Drift metrics computed and written.")
    print(f"   → Rows: {len(df)}")
    print(f"   → Updated file: {JOURNAL}")


if __name__ == "__main__":
    compute_drift()
