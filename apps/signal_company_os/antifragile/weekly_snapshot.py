# rhythm_os/antifragile/weekly_snapshot.py

import pandas as pd
from pathlib import Path
from ...kernel.wave import Wave  # three dots for one level up
from ...kernel.codex import Codex

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

LEDGER = DATA / "human" / "human_ledger.csv"
WEEKLY = DATA / "human" / "weekly_signatures.csv"

def run_weekly_wrapper():
    ledger = pd.read_csv(LEDGER)
    weekly = pd.read_csv(WEEKLY)

    print("══════════════════════════════════════")
    print("📘 WEEKLY WRAPPER — DIAGNOSTIC VIEW")
    print("══════════════════════════════════════")

    # rolling window
    window = ledger.tail(7)

    print(f"Rolling 7-day Avg Amplitude: {window['Amplitude'].mean():.4f}")
    print(f"Rolling 7-day Avg Resonance: {window['ResonanceValue'].mean():.4f}")

    if weekly.empty:
        print("⚠️ No canonical weekly memory yet.")
        return

    last_week = weekly.iloc[-1]
    print("--------------------------------------")
    print("Canonical Weekly Memory:")
    print(f" WeekEnd:        {last_week['WeekEnd']}")
    print(f" AvgAmplitude:   {last_week['AvgAmplitude']}")
    print(f" AvgResonance:   {last_week['AvgResonance']}")
    print("══════════════════════════════════════")

if __name__ == "__main__":
    run_weekly_wrapper()
