"""
Lighthouse — features.py (V1)

Builds feature matrices for Lighthouse using signal_journal.csv.

Targets:
    - y_state_next: next-day SignalState (classification)
    - y_change: today's ChangeType (classification)
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Dict

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]  # → .../SignalLogic/rhythm_os
DATA_DIR = ROOT / "data"
JOURNAL_PATH = DATA_DIR / "journal" / "signal_journal.csv"


CATEGORICAL_COLS = ["Season", "SignalState", "Phase"]
NUMERIC_COLS = [
    "SP500Close",
    "VIXClose",
    "TempAvg",
    "MoonIllum",
    "MoonAge",
    "Amplitude",
    "A_t",
    "C_t",
    "E_t",
    "H_t",
    "phi_h",
    "phi_e",
    "HSTResDrift",
    "HSTAmpCorr",
    "HSTTempCorr",
    "HSTPhaseDiv",
]


def _load_journal() -> pd.DataFrame:
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"signal_journal.csv not found at {JOURNAL_PATH}. "
            f"Run: python -m rhythm_os.core.kernel and journal.build first."
        )

    df = pd.read_csv(JOURNAL_PATH)

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Parse dates
    if "Date" not in df.columns:
        raise ValueError("signal_journal.csv is missing 'Date' column.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    return df


def build_supervised_frames() -> Tuple[pd.DataFrame, pd.Series, pd.Series, Dict]:
    """
    Builds:
        X        : features for supervised learning
        y_state  : next-day SignalState (y_state_next)
        y_change : today's ChangeType
        meta     : dict with Date index and any other metadata

    Assumes journal already has:
        - Season, SignalState, Phase
        - SP500Close, VIXClose, TempAvg, MoonIllum, MoonAge, Amplitude
        - A_t, C_t, E_t, H_t, phi_h, phi_e
        - HSTResDrift, HSTAmpCorr, HSTTempCorr, HSTPhaseDiv
    """
    df = _load_journal()

    # Build next-day label: y_state_next
    df["SignalState_next"] = df["SignalState"].shift(-1)

    # Drop last row (no next-day label yet)
    df = df.iloc[:-1].copy()

    # Targets
    y_state = df["SignalState_next"].astype(str)
    y_change = df["ChangeType"].astype(str) if "ChangeType" in df.columns else None

    # Features: one-hot encode categoricals, keep numerics
    feature_df = df[CATEGORICAL_COLS + NUMERIC_COLS].copy()

    # Fill missing numeric with simple strategy (mean)
    for col in NUMERIC_COLS:
        if col in feature_df.columns:
            col_values = pd.to_numeric(feature_df[col], errors="coerce")
            mean_val = col_values.mean()
            feature_df[col] = col_values.fillna(mean_val if not np.isnan(mean_val) else 0.0)

    # One-hot encode categoricals
    feature_df = pd.get_dummies(feature_df, columns=CATEGORICAL_COLS, dummy_na=False)

    meta = {
        "dates": df["Date"].tolist(),
    }

    return feature_df, y_state, y_change, meta


def build_latest_feature_row() -> pd.DataFrame:
    """
    Returns a single-row DataFrame of features for the most recent
    journal date, with the same columns as the training X.

    This is used by predict.py for daily inference.
    """
    # Build full supervised frames to get training columns
    X, _, _, _ = build_supervised_frames()
    train_cols = X.columns.tolist()

    df = _load_journal()
    latest = df.iloc[[-1]].copy()  # keep as DataFrame

    feature_df = latest[CATEGORICAL_COLS + NUMERIC_COLS].copy()

    for col in NUMERIC_COLS:
        if col in feature_df.columns:
            col_values = pd.to_numeric(feature_df[col], errors="coerce")
            # For a single row, just fill NaNs with 0.0
            feature_df[col] = col_values.fillna(0.0)

    feature_df = pd.get_dummies(feature_df, columns=CATEGORICAL_COLS, dummy_na=False)

    # Align columns to training set
    for col in train_cols:
        if col not in feature_df.columns:
            feature_df[col] = 0.0

    feature_df = feature_df[train_cols]

    return feature_df


if __name__ == "__main__":
    X, y_state, y_change, meta = build_supervised_frames()
    print("Features shape:", X.shape)
    print("State labels:", y_state.value_counts())
    if y_change is not None:
        print("ChangeType labels:", y_change.value_counts())
