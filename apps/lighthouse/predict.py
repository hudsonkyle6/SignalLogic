"""
Lighthouse — Combined Daily Prediction Output
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from rhythm_os.lighthouse.predict_state import predict_state
from rhythm_os.lighthouse.predict_resonance import predict_resonance

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
JOURNAL_PATH = DATA / "journal" / "signal_journal.csv"


def lighthouse_predict():
    # Run both predictions
    state_out = predict_state()
    res_out = predict_resonance()

    # Unify return
    return {
        "date": state_out["date"],
        "predicted_state": state_out["predicted_state"],
        "state_confidence": state_out["confidence"],
        "predicted_resonance": res_out["predicted_resonance"],
        "state_features": state_out["features_used"],
        "res_features": res_out["features_used"],
    }


if __name__ == "__main__":
    out = lighthouse_predict()

    print("══════════════════════════════════════════════")
    print("        📡 LIGHTHOUSE — DAILY PREDICTION")
    print("══════════════════════════════════════════════")
    print(f" Date used:          {out['date']}")
    print("──────────────────────────────────────────────")
    print(f" Predicted State:    {out['predicted_state']}")
    print(f"   Confidence:       {out['state_confidence']:.3f}")
    print(f" Predicted Resonance:{out['predicted_resonance']:.4f}")
    print("──────────────────────────────────────────────")
    print(f" State Model Features ({len(out['state_features'])}):")
    print(f"   {out['state_features']}")
    print(f" Resonance Features ({len(out['res_features'])}):")
    print(f"   {out['res_features']}")
    print("══════════════════════════════════════════════")
