"""
Rhythm OS — resonance_score.py (V4.1 — Governed Resonance, HST v3 + G(t) + Ghost)

Computes:
    • ResonanceRaw (Z-score, unbounded)
    • ResonanceValue (bounded [0,1], governed)
    • SignalState (Resonant / Still / Turbulent)
    • Phase (Emerging / Consolidating / Oscillating / Decaying / Anomalous)

    • Full HST v3:
        - A_t, C_t, E_t
        - H_t_base (pre-ghost)
        - G_t (ghost amplifier)
        - H_t (post-ghost)
        - phi_h, phi_e
        - HSTAmpCorr, HSTTempCorr, HSTPhaseDiv
        - HSTResDrift

    • Memory + Ghost:
        - MemoryDrift
        - MemoryPhaseCoherence
        - GhostStabilityIndex

Reads:
    data/merged/merged_signal.csv

Writes:
    data/merged/merged_signal.csv
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

from rhythm_os.utils.config import get_path


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

MERGED = os.path.join(get_path("paths.merged"), "merged_signal.csv")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def safe_z(series: pd.Series) -> pd.Series:
    """Numerically safe Z-score."""
    s = pd.to_numeric(series, errors="coerce")

    if s.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)

    sd = s.std(ddof=0)
    if sd == 0 or np.isclose(sd, 0.0) or pd.isna(sd):
        return pd.Series(0.0, index=series.index)

    return (s - s.mean()) / sd


def normalize_resonance(z: pd.Series) -> pd.Series:
    """Smooth, bounded, monotonic mapping → [0,1]."""
    return 1.0 / (1.0 + np.exp(-z))


def classify_state(res: float) -> str:
    if pd.isna(res):
        return "Still"
    if res >= 0.66:
        return "Resonant"
    if res <= 0.33:
        return "Turbulent"
    return "Still"


def classify_phase(res: float) -> str:
    if pd.isna(res):
        return "Oscillating"
    if res >= 0.66:
        return "Emerging"
    if res >= 0.50:
        return "Consolidating"
    if res > 0.33:
        return "Oscillating"
    if res > 0.20:
        return "Decaying"
    return "Anomalous"


def series_or_zero(df: pd.DataFrame, col: str) -> pd.Series:
    """Return numeric Series or zero-filled Series if column missing."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


# ------------------------------------------------------------
# HST v3 Core (pre-ghost)
# ------------------------------------------------------------

def compute_hst_core(amp: pd.Series, temp: pd.Series, moon: pd.Series):
    temp_z = safe_z(temp)
    amp_z = safe_z(amp)

    A_t = amp_z

    C_t = 1.0 - (abs(amp_z - temp_z) / 3.0)
    C_t = C_t.clip(-1, 1)

    E_t = (0.5 * temp_z) + (0.5 * moon)
    E_t = E_t.clip(-1, 1)

    H_t_core = (A_t + C_t + E_t) / 3.0

    phi_h = np.arctan2(C_t, A_t).astype(float)
    phi_e = np.arctan2(moon, temp_z).astype(float)

    def rol_corr(a, b):
        return a.rolling(7, min_periods=2).corr(b).fillna(0.0)

    HSTAmpCorr = rol_corr(A_t, temp_z)
    HSTTempCorr = rol_corr(temp_z, moon)
    HSTPhaseDiv = abs(phi_h - phi_e)

    return (
        A_t,
        C_t,
        E_t,
        H_t_core,
        phi_h,
        phi_e,
        HSTAmpCorr,
        HSTTempCorr,
        HSTPhaseDiv,
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def run_resonance():
    print("📡 Running resonance_score.py (V4.1 — Governed Resonance)")

    if not os.path.exists(MERGED):
        raise FileNotFoundError(f"Missing merged_signal.csv → {MERGED}")

    df = pd.read_csv(MERGED)

    # --------------------------------------------------------
    # Core numeric hygiene
    # --------------------------------------------------------

    df["Amplitude"] = pd.to_numeric(df.get("Amplitude"), errors="coerce").fillna(0.0)
    df["TempAvg"] = pd.to_numeric(df.get("TempAvg", 0.0), errors="coerce").fillna(0.0)
    df["MoonIllum"] = pd.to_numeric(df.get("MoonIllum", 0.0), errors="coerce").clip(0, 1).fillna(0.0)

    # --------------------------------------------------------
    # Resonance (raw → governed)
    # --------------------------------------------------------

    df["ResonanceRaw"] = safe_z(df["Amplitude"])
    df["ResonanceValue"] = normalize_resonance(df["ResonanceRaw"])

    df["SignalState"] = df["ResonanceValue"].apply(classify_state)
    df["Phase"] = df["ResonanceValue"].apply(classify_phase)

    # --------------------------------------------------------
    # Memory
    # --------------------------------------------------------

    afterglow = series_or_zero(df, "Afterglow")
    df["MemoryDrift"] = afterglow.diff().fillna(0.0)

    mem_phase = series_or_zero(df, "MemoryPhase")
    env_phase = (2.0 * np.pi * df["MoonIllum"]) % (2.0 * np.pi)

    df["MemoryPhaseCoherence"] = np.cos(mem_phase - env_phase)

    # --------------------------------------------------------
    # Ghost Stability Index
    # --------------------------------------------------------

    ghost = series_or_zero(df, "GhostLevel")
    wvi = series_or_zero(df, "WVI")

    amp_norm = (df["Amplitude"].abs() / (df["Amplitude"].abs().max() + 1e-6)).clip(0, 1)

    df["GhostStabilityIndex"] = (
        1.0
        - (0.4 * amp_norm)
        - (0.3 * ghost.clip(0, 1))
        - (0.3 * wvi.clip(0, 1))
    ).clip(0, 1)

    # --------------------------------------------------------
    # HST v3 Core
    # --------------------------------------------------------

    (
        df["A_t"],
        df["C_t"],
        df["E_t"],
        df["H_t_base"],
        df["phi_h"],
        df["phi_e"],
        df["HSTAmpCorr"],
        df["HSTTempCorr"],
        df["HSTPhaseDiv"],
    ) = compute_hst_core(
        amp=df["Amplitude"],
        temp=df["TempAvg"],
        moon=df["MoonIllum"],
    )

    # --------------------------------------------------------
    # G(t) — Ghost Amplifier
    # --------------------------------------------------------

    mem01 = (df["MemoryPhaseCoherence"] + 1.0) / 2.0
    ghost_stab = df["GhostStabilityIndex"].fillna(0.5)

    raw = (mem01 + ghost_stab) / 2.0

    beta = 0.5
    df["G_t"] = (1.0 + beta * (raw - 0.5)).clip(0.5, 1.5)

    df["H_t"] = df["H_t_base"] * df["G_t"]
    df["HSTResDrift"] = df["H_t"].diff().fillna(0.0)

    # --------------------------------------------------------
    # GhostFlag
    # --------------------------------------------------------

    if "GhostFlag" not in df.columns:
        df["GhostFlag"] = 0
    df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    df.to_csv(MERGED, index=False)

    print("   → Resonance + HST v3 + Ghost written")
    print(f"   → Rows: {len(df)}")


if __name__ == "__main__":
    run_resonance()
