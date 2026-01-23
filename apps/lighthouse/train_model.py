"""
Lighthouse V1 — train_model.py
--------------------------------
Trains predictive models for:
    • Next-day SignalState (classification)
    • Next-day ResonanceValue (regression)

Includes:
    • journal cleaner
    • antifragile feature builder
    • model trainers
    • model persistence
"""

import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, r2_score

import joblib


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
JOURNAL_PATH = DATA / "journal" / "signal_journal.csv"
MODEL_DIR = DATA / "models"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Cleaner — Remove infinities / NaNs / crazy large values
# ---------------------------------------------------------

def clean_journal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitizes the dataset so ML models don't explode.
    - Replace inf / -inf with NaN
    - Fill NaN with 0
    - Clip Pearson/HST metrics to [-5, 5]
    """

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.fillna(0.0)

    float_cols = df.select_dtypes(include=["float", "int"]).columns
    df[float_cols] = df[float_cols].clip(-5, 5)

    return df


# ---------------------------------------------------------
# Feature Builder (Antifragile)
# ---------------------------------------------------------

FEATURE_COLS = [
    "SP500Close", "VIXClose", "TempAvg", "MoonIllum",
    "Amplitude", "ResonanceValue",

    # HST Fields
    "A_t", "C_t", "E_t", "H_t",
    "phi_h", "phi_e", "HSTResDrift",
    "HSTAmpCorr", "HSTTempCorr", "HSTPhaseDiv",

    # Coupling metrics
    "CouplingLag", "CouplingPearson",
    "AmpCouplingLag", "AmpCouplingPearson",

    # Memory + Ghost (numeric only)
    "MemoryCharge", "Afterglow",
    "MemoryDrift", "MemoryPhaseCoherence",
    "GhostStabilityIndex",

    # Environmental forcing
    "WVI", "EnvPressure", "EnvFactor",
]




def select_available_features(df: pd.DataFrame):
    """
    Antifragile feature selector:
    Returns only the features that actually exist in the dataset.
    Prevents model failures if a field is missing.
    """
    return [c for c in FEATURE_COLS if c in df.columns]


# ---------------------------------------------------------
# Train classification model: Predict SignalState
# ---------------------------------------------------------

def train_state_model(df: pd.DataFrame):

    print("\n📡 Training State Model (RandomForestClassifier)...")

    # Encode target labels
    le = LabelEncoder()
    df["StateLabel"] = le.fit_transform(df["SignalState"])

    # Adaptive feature selection
    available = select_available_features(df)
    print(f"Using {len(available)} feature(s) for state model.")

    X = df[available].copy()
    y = df["StateLabel"]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, shuffle=False
    )

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        random_state=42,
        class_weight="balanced"
    )

    model.fit(X_train, y_train)

    # Performance
    preds = model.predict(X_test)
    print(classification_report(y_test, preds, target_names=le.classes_))

    # Save model + encoder
    joblib.dump(model, MODEL_DIR / "state_model.joblib")
    joblib.dump(le, MODEL_DIR / "state_label_encoder.joblib")

    print("✓ State model saved.")
    return model


# ---------------------------------------------------------
# Train regression model: Predict ResonanceValue
# ---------------------------------------------------------

def train_resonance_model(df: pd.DataFrame):

    print("\n📡 Training Resonance Regression Model (RandomForestRegressor)...")

    # Adaptive feature selection
    available = select_available_features(df)
    print(f"Using {len(available)} feature(s) for resonance model.")

    X = df[available].copy()
    y = df["ResonanceValue"]

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, shuffle=False
    )

    model = RandomForestRegressor(
        n_estimators=600,
        max_depth=12,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Performance
    preds = model.predict(X_test)
    print(f"\nR² score (test set): {r2_score(y_test, preds):.4f}")

    # Save
    joblib.dump(model, MODEL_DIR / "resonance_model.joblib")
    print("✓ Resonance model saved.")
    return model


# ---------------------------------------------------------
# Main training runner
# ---------------------------------------------------------

def main():

    print("📡 Lighthouse V1 — Training models from signal_journal.csv")

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(f"Journal missing: {JOURNAL_PATH}")

    df = pd.read_csv(JOURNAL_PATH)

    # Clean before ML
    df = clean_journal(df)

    # Remove incomplete rows
    df = df[df["ResonanceValue"].notna()]

    # Train models
    train_state_model(df)
    train_resonance_model(df)

    print("\n✨ Lighthouse V1 training complete.")
    print(f"   Models saved → {MODEL_DIR}")


if __name__ == "__main__":
    main()
