# rhythm_os/core/memory/afterglow.py

"""
AFTERGLOW / MEMORY — FROZEN PHYSICS MODULE (v1.0)

Role:
- Temporal inertia
- Decay of prior resonance
- Memory persistence without authority

Governance:
- Assist Under Discipline
- This module may retain influence but may not
  initiate, escalate, or compel action.

Freeze Record:
- ghost_freeze_v1.0.yaml
"""



from __future__ import annotations
from pathlib import Path
try:
    import pandas as pd
    import numpy as np
except ImportError as _e:
    raise ImportError(
        "numpy and pandas are required for memory analytics. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e

ROOT = Path(__file__).resolve().parents[2]


def _safe_col(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    """
    Return a column if it exists, otherwise a constant series.
    """
    if name in df.columns:
        return df[name].astype(float).fillna(default)
    return pd.Series([default] * len(df), index=df.index, dtype=float)


def _normalize(series: pd.Series, eps: float = 1e-9) -> pd.Series:
    """
    Simple 0–1 normalization, robust to constant series.
    """
    s = series.astype(float)
    s = s.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    min_v = s.min()
    max_v = s.max()
    if max_v - min_v < eps:
        return pd.Series(0.0, index=s.index)
    return (s - min_v) / (max_v - min_v)


def _load_latest_human_ledger() -> pd.DataFrame | None:
    """
    Load human_ledger.csv and return with Date parsed.
    If not present, return None (physics-only mode).
    """
    ledger_path = ROOT / "data" / "human" / "human_ledger.csv"
    if not ledger_path.exists():
        return None
    try:
        df = pd.read_csv(ledger_path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df.sort_values("Date")
        return df
    except Exception:
        # Fail closed: no ledger, no human contribution
        return None


def compute_memory_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attach Hybrid Event Field to merged_signal:

        • EventIntensity
        • MemoryCharge
        • Afterglow
        • MemoryPhase

    Hybrid = physics + environment + human.

    Physics:
        - |ΔResonanceValue|
        - |ΔAmplitude|
        - |HSTResDrift|
        - WVI spike vs rolling baseline

    Human (if ledger is available):
        - BodyLoad
        - Stress
        - (5 - Clarity)   # low clarity = more "event pressure"
    """
    if df.empty:
        return df

    df = df.copy()

    # ------------------------------------------------------------------
    # 0. Ensure Date is a real datetime and sorted
    # ------------------------------------------------------------------
    if "Date" in df.columns:
        try:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=False)
        except Exception:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # ------------------------------------------------------------------
    # 1. Base series (physics side)
    # ------------------------------------------------------------------
    res = _safe_col(df, "ResonanceValue", default=0.0)
    amp = _safe_col(df, "Amplitude", default=0.0)
    drift = _safe_col(df, "HSTResDrift", default=0.0)
    wvi = _safe_col(df, "WVI", default=0.0)

    # Day-to-day changes
    d_res = (res - res.shift(1)).abs().fillna(0.0)
    d_amp = (amp - amp.shift(1)).abs().fillna(0.0)

    # WVI spike relative to a 14-day rolling baseline
    wvi_baseline = wvi.rolling(window=14, min_periods=3).mean()
    wvi_spike = (wvi - wvi_baseline).clip(lower=0.0).fillna(0.0)

    # Normalize these components so we can mix them
    d_res_n = _normalize(d_res)
    d_amp_n = _normalize(d_amp)
    drift_n = _normalize(drift.abs())
    wvi_n = _normalize(wvi_spike)

    physics_intensity = (
        0.40 * d_res_n +
        0.25 * d_amp_n +
        0.20 * drift_n +
        0.15 * wvi_n
    )

    # ------------------------------------------------------------------
    # 2. Human side (optional, via ledger)
    # ------------------------------------------------------------------
    ledger = _load_latest_human_ledger()
    human_intensity = pd.Series(0.0, index=df.index)

    if ledger is not None and "Date" in df.columns and "Date" in ledger.columns:
        # Reduce ledger to latest entry per date
        ledger = ledger.sort_values("Date").drop_duplicates("Date", keep="last")

        # Select useful cols if they exist
        # (we're defensive here to avoid KeyErrors)
        for c in ["BodyLoad", "Stress", "Clarity"]:
            if c not in ledger.columns:
                ledger[c] = 0

        # Merge by Date (left join on world signal)
        merged = df[["Date"]].merge(
            ledger[["Date", "BodyLoad", "Stress", "Clarity"]],
            on="Date", how="left"
        )

        body = merged["BodyLoad"].fillna(0.0).astype(float)
        stress = merged["Stress"].fillna(0.0).astype(float)
        clarity = merged["Clarity"].fillna(0.0).astype(float)

        # Scale 1-5 human scores to 0-1
        body_n = (body / 5.0).clip(0.0, 1.0)
        stress_n = (stress / 5.0).clip(0.0, 1.0)
        # lower clarity => higher "event pressure"
        clarity_n = ((5.0 - clarity) / 5.0).clip(0.0, 1.0)

        human_intensity = (
            0.40 * body_n +
            0.40 * stress_n +
            0.20 * clarity_n
        )

    # ------------------------------------------------------------------
    # 3. Hybrid EventIntensity
    # ------------------------------------------------------------------
    raw_intensity = physics_intensity + human_intensity

    # Small noise cutoff – below this we treat as no discernible event
    threshold = raw_intensity.quantile(0.35)  # 35th percentile
    event_intensity = (raw_intensity - threshold).clip(lower=0.0)

    # Normalize EventIntensity to [0, 1] for interpretability
    event_intensity = _normalize(event_intensity)

    df["EventIntensity"] = event_intensity

    # ------------------------------------------------------------------
    # 4. MemoryCharge (decay + accumulation)
    # ------------------------------------------------------------------
    memory_charge = []
    charge_prev = 0.0
    decay = 0.90       # 10% per day decay
    gain = 0.85        # how strongly new events charge memory

    for v in event_intensity:
        charge_today = decay * charge_prev + gain * float(v)
        memory_charge.append(charge_today)
        charge_prev = charge_today

    memory_charge = pd.Series(memory_charge, index=df.index)
    memory_charge = memory_charge.clip(lower=0.0)

    # Normalize again for Afterglow so it's 0-1
    afterglow = _normalize(memory_charge)

    df["MemoryCharge"] = memory_charge
    df["Afterglow"] = afterglow

    # ------------------------------------------------------------------
    # 5. MemoryPhase – qualitative label
    # ------------------------------------------------------------------
    phase = []
    for mc, ai in zip(afterglow, event_intensity):
        if mc < 0.05 and ai < 0.05:
            phase.append("QUIET")
        elif ai >= 0.10:
            phase.append("ACTIVE")
        else:
            phase.append("DECAY")

    df["MemoryPhase"] = phase

    return df
