import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
HUMAN_DIR = DATA_DIR / "human"
HUMAN_LEDGER_PATH = HUMAN_DIR / "human_ledger.csv"

from ...kernel.wave import Wave
from ...kernel.codex import Codex


def ensure_human_dirs():
    HUMAN_DIR.mkdir(parents=True, exist_ok=True)


def _latest_row():
    if not HUMAN_LEDGER_PATH.exists():
        raise FileNotFoundError(
            f"human_ledger.csv not found at {HUMAN_LEDGER_PATH}. "
            "Run the ledger first."
        )

    df = pd.read_csv(HUMAN_LEDGER_PATH)
    if df.empty:
        raise ValueError("human_ledger.csv is empty.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    return df.iloc[-1]


def _score_compass(latest: pd.Series) -> str:
    """
    Heuristic decision engine based on:

      Human Strain:
        + BodyLoad, Resistance, StressLevel (higher = more strain)
        - Clarity, SleepQuality, EnvFeel   (higher = more capacity)

      Environmental Pressure:
        + EnvPressureIndex, SeasonalLoadIndex

    This is intentionally simple and interpretable.
    """

    def g(name, default=0.0):
        return float(latest.get(name, default) or 0.0)

    # Normalize 1–5 scale to 0–1
    def norm_5(x):
        return max(0.0, min(1.0, (x - 1.0) / 4.0))

    body = norm_5(g("BodyLoad"))
    resist = norm_5(g("Resistance"))
    stress = norm_5(g("StressLevel"))
    sleep = norm_5(g("SleepQuality"))
    clarity = norm_5(g("Clarity"))
    envfeel = norm_5(g("EnvFeel"))

    env_press = float(latest.get("EnvPressureIndex", 0.0) or 0.0)
    seasonal = float(latest.get("SeasonalLoadIndex", 0.5) or 0.5)

    # Human strain (0–1): high if body/resist/stress high and clarity/sleep low
    strain = (
        0.35 * body
        + 0.25 * resist
        + 0.25 * stress
        + 0.075 * (1.0 - clarity)
        + 0.075 * (1.0 - sleep)
    )

    # Human capacity (0–1): clarity + sleep + envfeel
    capacity = 0.4 * clarity + 0.4 * sleep + 0.2 * envfeel

    # Overall external pressure
    external = 0.6 * env_press + 0.4 * seasonal

    # Simple decision logic
    # WAIT: high strain OR high external pressure, low capacity
    if (strain >= 0.7 and capacity <= 0.4) or external >= 0.75:
        return "WAIT"

    # PUSH: very low strain, high capacity, low external pressure
    if strain <= 0.3 and capacity >= 0.7 and external <= 0.4:
        return "PUSH"

    # ACT / PREPARE: middle cases
    # ACT: capacity reasonably high and strain moderate
    if capacity >= 0.55 and strain <= 0.6 and external <= 0.7:
        return "ACT"

    # otherwise PREPARE
    return "PREPARE"


def run_compass():
    """
    CLI entry: compute CompassState for latest ledger entry,
    print it, and optionally write it back into the ledger.
    """
    ensure_human_dirs()
    latest = _latest_row()

    date_str = latest["Date"].strftime("%Y-%m-%d")
    human_state = latest.get("DecisionState", "")
    compass_state = _score_compass(latest)

    print("══════════════════════════════════════")
    print("        🧭 ANTIFRAGILE COMPASS")
    print("══════════════════════════════════════")
    print(f" Date:          {date_str}")
    print(f" Season:        {latest.get('Season', '')}")
    print("--------------------------------------")
    print(f" Ledger State:  {human_state}")
    print(f" Compass State: {compass_state}")
    print("──────────────────────────────────────")

    body = latest.get("BodyLoad", "")
    clarity = latest.get("Clarity", "")
    resist = latest.get("Resistance", "")
    envp = latest.get("EnvPressureIndex", "")
    envwin = latest.get("EnergyWindow", "")

    print(f" BodyLoad:      {body}")
    print(f" Clarity:       {clarity}")
    print(f" Resistance:    {resist}")
    print(f" EnvPressure:   {envp}")
    print(f" EnergyWindow:  {envwin}")
    print("──────────────────────────────────────")
    print(" Heuristic guidance:")
    if compass_state == "WAIT":
        print("  → Contract. Clear backlog. Protect capacity.")
    elif compass_state == "PREPARE":
        print("  → Align. Set foundations. Light work on key arcs.")
    elif compass_state == "ACT":
        print("  → Move. Execute planned work. Normal output.")
    elif compass_state == "PUSH":
        print("  → Rare window. Take the big swing (with respect).")
    print("══════════════════════════════════════")

    # Write CompassState back into ledger
    try:
        df = pd.read_csv(HUMAN_LEDGER_PATH)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        mask = df["Date"] == latest["Date"]
        if "CompassState" not in df.columns:
            df["CompassState"] = ""
        df.loc[mask, "CompassState"] = compass_state
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df.to_csv(HUMAN_LEDGER_PATH, index=False)
        print("✅ CompassState written back into human_ledger.csv")
    except Exception as e:
        print("⚠️ Could not write CompassState to ledger:", e)


if __name__ == "__main__":
    try:
        run_compass()
    except Exception as e:
        print("❌ Error:", e)
        sys.exit(1)
