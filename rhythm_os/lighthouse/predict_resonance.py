"""
Lighthouse V1 — predict_resonance.py

Predicts:
    • Next-day ResonanceValue (regression)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
import joblib

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
JOURNAL_PATH = DATA / "journal" / "signal_journal.csv"
MODEL_DIR = DATA / "models"


def predict_resonance():
    print("📡 Lighthouse — Predicting next-day ResonanceValue...")

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(f"Missing journal: {JOURNAL_PATH}")

    df = pd.read_csv(JOURNAL_PATH)

    if df.empty:
        raise ValueError("signal_journal.csv is empty — nothing to predict from.")

    # Latest row
    last = df.iloc[-1:].copy()

    # Load model
    model_path = MODEL_DIR / "resonance_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError("Resonance model not found in data/models.")

    model = joblib.load(model_path)

    # -------------------------------------------------------
    # ENFORCE TRAINED FEATURE SET (schema authority)
    # -------------------------------------------------------
    if not hasattr(model, "feature_names_in_"):
        raise RuntimeError(
            "Resonance model missing feature_names_in_. Retrain with updated train_model.py."
        )

    expected_features = list(model.feature_names_in_)

    # Align features exactly to training contract
    X = last.reindex(columns=expected_features)

    # Replace infinities / NaNs with safe defaults
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # -------------------------------------------------------
    # PREDICT
    # -------------------------------------------------------
    pred = float(model.predict(X)[0])

    print("──────────────────────────────────────────────")
    print(f" Latest date in journal: {last['Date'].iloc[0]}")
    print(f" Predicted ResonanceValue: {pred:.4f}")
    print(f" Features used ({len(expected_features)}): {expected_features}")
    print("──────────────────────────────────────────────")

    return {
        "date": last["Date"].iloc[0],
        "predicted_resonance": pred,
        "features_used": expected_features,
    }


if __name__ == "__main__":
    predict_resonance()

