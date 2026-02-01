"""
Rhythm OS — Amplitude Engine (V1, HST-Compatible)

Composite amplitude of the world:
    • SP500Close
    • VIXClose
    • TempAvg
    • MoonIllum
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from .smoothing import natural_smooth


def _zscore(series: pd.Series) -> pd.Series:
    """Safe z-score (returns 0 when std ~ 0)."""
    s = pd.to_numeric(series, errors="coerce")
    m = s.mean()
    sd = s.std(ddof=0)
    if sd is None or sd == 0 or np.isclose(sd, 0.0):
        return pd.Series(0.0, index=s.index)
    return (s - m) / sd


def compute_amplitude(df: pd.DataFrame) -> pd.Series:
    """
    Composite amplitude from all available drivers:

        • SP500Close
        • VIXClose
        • TempAvg
        • MoonIllum

    Steps:
        1. Convert each driver to z-score
        2. Per-day std dev of available drivers → raw amplitude
        3. Smooth via natural_smooth
        4. Normalize gently and clip to [-1, 1]

    Returns:
        pd.Series aligned with df.index
    """
    work = df.copy()
    drivers = []

    for col in ("SP500Close", "VIXClose", "TempAvg", "MoonIllum"):
        if col in work.columns:
            z = _zscore(work[col])
            drivers.append(z)

    if not drivers:
        return pd.Series(0.0, index=work.index)

    stack = np.vstack([d.values for d in drivers])
    amp_raw = np.nanstd(stack, axis=0)
    amp = pd.Series(amp_raw, index=work.index)

    # Smooth the shape
    amp = natural_smooth(amp)

    # Normalize to [-1, 1]
    if amp.notna().any():
        m = amp.mean()
        sd = amp.std(ddof=0)
        if sd and not np.isclose(sd, 0.0):
            amp_z = (amp - m) / sd
            return (amp_z.clip(-2, 2) / 2).fillna(0.0)

    return amp.fillna(0.0)
