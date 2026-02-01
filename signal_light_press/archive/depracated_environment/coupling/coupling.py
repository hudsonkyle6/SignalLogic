# rhythm_os/core/coupling/coupling.py
"""
Canonical Coupling Engine (HST-Aligned)

This module is the sole authority for coupling computation.
All other coupling modules must delegate to it.

Responsibilities:
    • Lagged Pearson correlation
    • Sample sufficiency enforcement
    • Single source of mathematical truth
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


# ======================================================================
# DATA STRUCTURE
# ======================================================================

@dataclass(frozen=True)
class CouplingStat:
    col: str
    lag_days: int
    n: int
    pearson: float
    note: str = ""


# ======================================================================
# CANONICAL COUPLING COMPUTATION
# ======================================================================

def compute_coupling(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    max_lag: int = 30,
    min_points: int = 7,
) -> Optional[CouplingStat]:
    """
    Search lag window [-max_lag, +max_lag] for strongest Pearson coupling
    between source_col and target_col.

    Returns CouplingStat or None if insufficient data.
    """

    if source_col not in df.columns or target_col not in df.columns:
        return None

    x = pd.to_numeric(df[source_col], errors="coerce")
    y = pd.to_numeric(df[target_col], errors="coerce")

    best: Optional[CouplingStat] = None
    best_abs = -1.0

    for lag in range(-max_lag, max_lag + 1):
        shifted = x.shift(lag)
        valid = pd.DataFrame({"x": shifted, "y": y}).dropna()
        n = len(valid)

        if n < min_points:
            continue

        pear = valid["x"].corr(valid["y"])
        if pear is None or np.isnan(pear):
            continue

        if abs(pear) > best_abs:
            best_abs = abs(pear)
            best = CouplingStat(
                col=source_col,
                lag_days=lag,
                n=n,
                pearson=float(pear),
            )

    return best
