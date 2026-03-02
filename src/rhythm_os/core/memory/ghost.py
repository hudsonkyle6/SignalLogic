# rhythm_os/core/memory/ghost.py

"""
GHOST LAYER — FROZEN PHYSICS MODULE (v1.0)

Role:
- Stability mass
- Anomaly damping
- Non-authoritative memory field

Governance:
- Assist Under Discipline
- This module may shape stability but may not initiate,
  escalate, or compel action.

Freeze Record:
- ghost_freeze_v1.0.yaml
"""

from __future__ import annotations

try:
    import pandas as pd
    import numpy as np
except ImportError as _e:
    raise ImportError(
        "numpy and pandas are required for ghost memory analytics. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e


# =====================================================================
#  PART 1 — YOUR ORIGINAL GHOST LAYER (kept exactly, untouched)
# =====================================================================


def inject_ghost_layer(df: pd.DataFrame) -> pd.DataFrame:
    """
    Original Ghost gap-filling logic.
    Preserved exactly so your system maintains continuity.
    """
    if df.empty:
        return df

    df = df.copy()

    if "GhostFlag" not in df.columns:
        df["GhostFlag"] = 0
    df["GhostFlag"] = df["GhostFlag"].fillna(0).astype(int)

    afterglow = df.get("Afterglow", pd.Series(0.0, index=df.index))

    ghost_cols = [
        "ResonanceValue",
        "Amplitude",
        "SP500Close",
        "VIXClose",
        "H_t",
    ]

    for col in ghost_cols:
        if col not in df.columns:
            continue

        series = df[col].astype(float)
        mask_nan = series.isna()

        if not mask_nan.any():
            continue

        interp = series.interpolate(method="linear", limit_direction="both")

        ghost_series = series.copy()
        ghost_series[mask_nan] = interp[mask_nan] * (0.7 + 0.3 * afterglow[mask_nan])

        df[col + "_ghosted"] = ghost_series
        df.loc[mask_nan, "GhostFlag"] = 1

    # Qualitative ghost level
    if "GhostFlag" in df.columns:
        levels = []
        for flag, ag in zip(df["GhostFlag"], afterglow):
            if flag == 0:
                levels.append("NONE")
            elif ag < 0.3:
                levels.append("GHOST_LIGHT")
            elif ag < 0.7:
                levels.append("GHOST_MEDIUM")
            else:
                levels.append("GHOST_HEAVY")
        df["GhostLevel"] = levels

    return df


# =====================================================================
#  PART 2 — FULL GHOST ENGINE (Stability, Drift, Phase, Governor, etc.)
# =====================================================================


def _sigmoid(x, k=1.0):
    x = np.asarray(x, dtype=float)
    return 1 / (1 + np.exp(-k * x))


def _normalize(series, vmin, vmax):
    span = vmax - vmin
    if span == 0:
        return pd.Series(0.5, index=series.index)
    return ((series - vmin) / span).clip(0, 1)


def _angle_wrap(delta):
    return (delta + np.pi) % (2 * np.pi) - np.pi


def compute_ghost_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full Ghost Engine (v1.0 production-ready).

    Produces:
        - Drift component
        - Phase component
        - Volatility component
        - GhostInstabilityRaw
        - GhostStabilityIndex
        - GhostMemoryPressure
        - MemoryChargeEff
        - AfterglowEff
        - GhostGovernor
        - GhostShadow (CLEAR/HAZE/SHADOW/VOID)
    """
    if df.empty:
        return df

    df = df.copy()

    # -----------------------------------------------------------------
    # DRIFT COMPONENT (how abnormal is today's drift?)
    # -----------------------------------------------------------------
    drift = df["HSTResDrift"].abs().fillna(0.0)
    roll = drift.rolling(window=30, min_periods=10)
    mu = roll.mean()
    sigma = roll.std().replace(0, np.nan).fillna(1.0)

    drift_z = (drift - mu) / sigma
    drift_z = drift_z.clip(lower=0.0)
    D_ghost = _sigmoid(drift_z, k=1.0)
    df["GhostDriftComponent"] = D_ghost

    # -----------------------------------------------------------------
    # PHASE COMPONENT (phase lock / unnatural alignment)
    # -----------------------------------------------------------------
    if "phi_h" in df.columns and "phi_e" in df.columns:
        delta_phi = _angle_wrap(df["phi_h"] - df["phi_e"])
        sigma_phi = np.pi / 12.0
        C_phase = np.exp(-(delta_phi**2) / (2 * sigma_phi**2))
    else:
        C_phase = pd.Series(0.5, index=df.index)

    df["GhostPhaseComponent"] = C_phase

    # -----------------------------------------------------------------
    # VOLATILITY COMPONENT (VIX + WVI + Amplitude delta)
    # -----------------------------------------------------------------
    vix_norm = _normalize(
        df.get("VIXClose", pd.Series(20.0, index=df.index)), 10.0, 40.0
    )

    wvi_norm = df.get("WVI", pd.Series(0.0, index=df.index)).clip(0, 1)

    amp = df.get("Amplitude", pd.Series(0.0, index=df.index)).fillna(0.0)
    amp_delta = amp.diff().abs().fillna(0.0)
    amp_norm = _normalize(amp_delta, 0.0, 0.2)

    V_ghost = 0.4 * vix_norm + 0.4 * wvi_norm + 0.2 * amp_norm
    df["GhostVolatilityComponent"] = V_ghost.clip(0, 1)

    # -----------------------------------------------------------------
    # GHOST INSTABILITY + STABILITY INDEX
    # -----------------------------------------------------------------
    alpha_D = 0.4
    alpha_P = 0.3
    alpha_V = 0.3

    Instability = alpha_D * D_ghost + alpha_P * C_phase + alpha_V * V_ghost
    Instability = Instability.clip(0, 1)

    df["GhostInstabilityRaw"] = Instability
    df["GhostStabilityIndex"] = 1.0 - Instability

    # -----------------------------------------------------------------
    # MEMORY PRESSURE + EFFECTIVE MEMORY
    # -----------------------------------------------------------------
    mem_drift = df.get("MemoryDrift", pd.Series(0.0, index=df.index)).abs()
    MemoryPressure = (mem_drift * (1 - df["GhostStabilityIndex"])).clip(0, 1)
    df["GhostMemoryPressure"] = MemoryPressure

    if "MemoryCharge" in df.columns:
        df["MemoryChargeEff"] = df["MemoryCharge"] * (1 - 0.5 * MemoryPressure)
    else:
        df["MemoryChargeEff"] = np.nan

    # AFTERGLOW EFFECT
    if "Afterglow" in df.columns:
        df["AfterglowEff"] = df["Afterglow"] * (1 - 0.5 * V_ghost)
    else:
        df["AfterglowEff"] = np.nan

    # -----------------------------------------------------------------
    # GHOST GOVERNOR (throttle)
    # -----------------------------------------------------------------
    InstabilitySmooth = Instability.ewm(alpha=0.2, adjust=False).mean()
    df["GhostInstabilitySmooth"] = InstabilitySmooth

    kappa = 0.7
    df["GhostGovernor"] = (1 - kappa * InstabilitySmooth).clip(0.3, 1.0)

    # -----------------------------------------------------------------
    # GHOSTSHADOW qualitative mode
    # -----------------------------------------------------------------
    shadow = []
    for gsi, vol in zip(df["GhostStabilityIndex"], V_ghost):
        if gsi > 0.75 and vol < 0.3:
            shadow.append("CLEAR")
        elif gsi > 0.40:
            shadow.append("HAZE")
        elif gsi > 0.20:
            shadow.append("SHADOW")
        else:
            shadow.append("VOID")

    df["GhostShadow"] = shadow

    return df
