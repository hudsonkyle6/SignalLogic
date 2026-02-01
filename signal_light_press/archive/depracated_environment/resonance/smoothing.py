"""
Rhythm OS — Resonance Smoothing Algorithms (V1)

Philosophy:
    • Simple
    • Gentle
    • Natural

We avoid harsh filtering.
Nature smooths through decay, continuity, and pressure equalization.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# 1. Linear gap interpolation (tiny gaps only)
# ---------------------------------------------------------------------

def smooth_linear(series: pd.Series, limit: int = 3) -> pd.Series:
    """
    Fill small NaN gaps using linear interpolation.

    Used for:
        • MoonIllum
        • TempAvg
        • small amplitude gaps
    """
    return series.interpolate(
        method="linear",
        limit=limit,
        limit_direction="both"
    )


# ---------------------------------------------------------------------
# 2. 3-point natural smoothing (gentle)
# ---------------------------------------------------------------------

def smooth_three_point(series: pd.Series) -> pd.Series:
    """
    3-point smoothing:
        s[i] = (prev + current + next) / 3

    Common in:
        • tide harmonics
        • tree ring growth curves
        • glacial pressure changes

    Very gentle — preserves wave structure.
    """
    values = series.to_numpy(dtype=float)
    out = np.copy(values)

    for i in range(1, len(values) - 1):
        if np.isnan(values[i]):
            continue

        prev_val = values[i - 1]
        next_val = values[i + 1]

        if not np.isnan(prev_val) and not np.isnan(next_val):
            out[i] = (prev_val + values[i] + next_val) / 3.0

    return pd.Series(out, index=series.index)
# ---------------------------------------------------------------------
# Memory smoothing helpers
# ---------------------------------------------------------------------

def smooth_memory_charge(series: pd.Series, limit: int = 5) -> pd.Series:
    """
    Smooth MemoryCharge using a gentle rolling mean + interpolation.

    - limit: window for rolling mean
    """
    if series.isna().all():
        return series

    smoothed = series.copy()
    smoothed = smoothed.interpolate(
        method="linear", limit=limit, limit_direction="both"
    )
    smoothed = smoothed.rolling(window=limit, min_periods=1, center=True).mean()
    return smoothed


def smooth_afterglow(series: pd.Series, limit: int = 5) -> pd.Series:
    """
    Smooth Afterglow using the same style as MemoryCharge.
    """
    return smooth_memory_charge(series, limit=limit)


# ---------------------------------------------------------------------
# 3. Savitzky–Golay–lite (5-point poly filter)
# ---------------------------------------------------------------------

def smooth_savgol_lite(series: pd.Series) -> pd.Series:
    """
    A minimal Savitzky-Golay approximation WITHOUT scipy.

    5-point window, quadratic fit.
    Preserves:
        • phase alignment
        • peaks and troughs
        • long seasonal waves
    """
    vals = series.to_numpy(dtype=float)
    out = np.copy(vals)

    n = len(vals)
    if n < 5:
        return series.copy()

    for i in range(2, n - 2):
        window = vals[i - 2:i + 3]
        if np.isnan(window).any():
            continue

        # SG 5-point quadratic coefficients
        out[i] = (
            -3 * vals[i - 2] +
            12 * vals[i - 1] +
            17 * vals[i] +
            12 * vals[i + 1] -
            3 * vals[i + 2]
        ) / 35.0

    return pd.Series(out, index=series.index)


# ---------------------------------------------------------------------
# 4. Composite Natural Smoother — official Rhythm OS profile
# ---------------------------------------------------------------------

def natural_smooth(series: pd.Series) -> pd.Series:
    """
    Rhythm OS “Nature Smoother” profile:

        1. Linear interpolate tiny gaps (limit=3)
        2. Gentle 3-point smoothing
        3. SG-lite harmonic smoothing

    Produces curves that behave like:
        • atmospheric pressure transitions
        • daily resonance drift
        • longwave seasonal harmonics
    """
    s = smooth_linear(series, limit=3)
    s = smooth_three_point(s)
    s = smooth_savgol_lite(s)
    return s

