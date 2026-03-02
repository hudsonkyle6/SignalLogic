"""
Lighthouse V1 — predict_state.py

Predicts:
    • Next-day SignalState (classification)
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


def predict_state():
    print("📡 Lighthouse — Predicting next-day SignalState...")

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(f"Missing journal: {JOURNAL_PATH}")

    df = pd.read_csv(JOURNAL_PATH)

    if df.empty:
        raise ValueError("signal_journal.csv is empty — nothing to predict from.")

    # Latest row
    last = df.iloc[-1:].copy()

    # Load model + encoder
    model_path = MODEL_DIR / "state_model.joblib"
    enc_path = MODEL_DIR / "state_label_encoder.joblib"

    if not model_path.exists() or not enc_path.exists():
        raise FileNotFoundError(
            "State model or label encoder not found in data/models."
        )

    model = joblib.load(model_path)
    label_enc = joblib.load(enc_path)

    # -------------------------------------------------------
    # ENFORCE TRAINED FEATURE SET (schema authority)
    # -------------------------------------------------------
    if not hasattr(model, "feature_names_in_"):
        raise RuntimeError(
            "Model is missing feature_names_in_. Retrain with updated train_model.py."
        )

    expected_features = list(model.feature_names_in_)

    # Start from whatever overlap exists
    X = last.reindex(columns=expected_features)

    # Replace infinities / NaNs with safe defaults
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # -------------------------------------------------------
    # PREDICT
    # -------------------------------------------------------
    probs = model.predict_proba(X)[0]
    idx = int(np.argmax(probs))
    state = label_enc.inverse_transform([idx])[0]
    conf = float(probs[idx])

    print("──────────────────────────────────────────────")
    print(f" Latest date in journal: {last['Date'].iloc[0]}")
    print(f" Predicted State:  {state}")
    print(f" Confidence:       {conf:.3f}")
    print(f" Features used ({len(expected_features)}): {expected_features}")
    print("──────────────────────────────────────────────")

    return {
        "date": last["Date"].iloc[0],
        "predicted_state": state,
        "confidence": conf,
        "features_used": expected_features,
    }


if __name__ == "__main__":
    predict_state()
