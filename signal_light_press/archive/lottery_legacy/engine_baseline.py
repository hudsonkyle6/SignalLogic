# engine_baseline.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Baseline:
    recent_mean_amp: float
    recent_std_amp: float
    latest_amp: float
    z: float
    z_robust: float
    z_ema: float
    z_roll: float
    z_tail: List[float]

def _safe_float(x) -> float:
    try:
        xf = float(x)
        if np.isnan(xf):
            return float("nan")
        return xf
    except Exception:
        return float("nan")

def _mad(series: pd.Series) -> float:
    """Median Absolute Deviation (scaled to ~std for normal data)."""
    med = series.median()
    mad = (series - med).abs().median()
    # 1.4826 scales MAD to be comparable to std under normal dist.
    return 1.4826 * float(mad)

def compute_baseline(
    df_in: pd.DataFrame,
    *,
    window_days: int = 56,
    window_count: Optional[int] = None,
    alpha: float = 0.25,         # EMA smoothing factor
) -> Baseline:
    """
    Build contextual metrics over a recent window.
    Requires df_in to contain Date (datetime), delta, amp (from compute_rhythm).

    Choose either:
      - window_count = last N draws, OR
      - window_days  = last X days (default)
    """
    df = df_in.copy()
    # Ensure expected columns
    if "Date" not in df.columns:
        raise ValueError("Baseline expects a 'Date' column.")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # If amp/delta are missing (defensive)
    if "delta" not in df.columns:
        df["delta"] = df["sum"].diff() if "sum" in df.columns else pd.NA
    if "amp" not in df.columns:
        df["amp"] = df["delta"].abs()

    # Pick recent window
    if window_count and window_count > 1:
        recent = df.tail(window_count).copy()
    else:
        cutoff = df["Date"].max() - pd.Timedelta(days=window_days)
        recent = df[df["Date"] >= cutoff].copy()
        if recent.empty:
            recent = df.copy()

    # Amplitude stats
    recent["amp"] = pd.to_numeric(recent["amp"], errors="coerce")
    recent = recent.dropna(subset=["amp"])
    if len(recent) == 0 or len(df) < 2:
        return Baseline(
            recent_mean_amp=float("nan"),
            recent_std_amp=float("nan"),
            latest_amp=float("nan"),
            z=0.0, z_robust=0.0, z_ema=0.0, z_roll=0.0, z_tail=[],
        )

    latest_amp = _safe_float(df["amp"].iloc[-1])
    mean8 = _safe_float(recent["amp"].mean())
    std8  = _safe_float(recent["amp"].std(ddof=1)) if len(recent) > 1 else 0.0

    # Standard z
    if std8 and std8 > 0:
        z_series = (df["amp"] - mean8) / std8
        z_latest = _safe_float(z_series.iloc[-1])
    else:
        z_series = pd.Series(0.0, index=df.index)
        z_latest = 0.0

    # Robust z (median/MAD)
    med = _safe_float(recent["amp"].median())
    mad = _mad(recent["amp"])
    if mad and mad > 0:
        z_robust_series = (df["amp"] - med) / mad
        z_robust_latest = _safe_float(z_robust_series.iloc[-1])
    else:
        z_robust_latest = 0.0

    # EMA mean/std → EMA z
    # Compute simple EMA mean of recent window, and EMA of |amp-EMA_mean|
    # (a lightweight volatility proxy), then z_ema = (latest-ema_mean)/ema_std
    ema_mean = recent["amp"].ewm(alpha=alpha, adjust=False).mean()
    # mean absolute deviation around EMA mean, scaled ~std
    ema_dev  = (recent["amp"] - ema_mean).abs().ewm(alpha=alpha, adjust=False).mean() * 1.253
    ema_mean_latest = _safe_float(ema_mean.iloc[-1])
    ema_std_latest  = _safe_float(ema_dev.iloc[-1])
    z_ema_latest = ((latest_amp - ema_mean_latest) / ema_std_latest) if (ema_std_latest and ema_std_latest > 0) else 0.0

    # Rolling 5-run average of standard z
    z_roll_series = z_series.rolling(window=5, min_periods=1).mean()
    z_roll_latest = _safe_float(z_roll_series.iloc[-1])
    z_tail = [float(x) for x in z_roll_series.tail(25).fillna(0.0).tolist()]

    return Baseline(
        recent_mean_amp=_safe_float(mean8),
        recent_std_amp=_safe_float(std8),
        latest_amp=_safe_float(latest_amp),
        z=_safe_float(z_latest),
        z_robust=_safe_float(z_robust_latest),
        z_ema=_safe_float(z_ema_latest),
        z_roll=_safe_float(z_roll_latest),
        z_tail=z_tail,
    )
