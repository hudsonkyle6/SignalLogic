# rhythm_os/core/coupling/coupling.py
"""
POSTURE: TURBINE (READ-ONLY)

Consumes Penstock flow.
Produces diagnostics only.
No authority.
Canonical Coupling Engine (HST-Aligned)

This module is the sole authority for coupling computation.
All other coupling modules must delegate to it.

Responsibilities:
    • Lagged Pearson correlation
    • Sample sufficiency enforcement
    • Deterministic tie-breaking
    • Single source of mathematical truth

Notes:
    • Coupling is symmetric and non-causal.
    • Lag indicates alignment offset, not direction of influence.
    • This module performs no interpretation, gating, emission, or persistence.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

try:
    import numpy as np
    import pandas as pd
except ImportError as _e:
    raise ImportError(
        "numpy and pandas are required for coupling analytics. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e


# ======================================================================
# DATA STRUCTURE
# ======================================================================


@dataclass(frozen=True)
class CouplingStat:
    """
    Immutable coupling description.

    Fields:
        col        : source column name
        lag_days   : lag (positive or negative) applied to source
        n          : number of paired samples used
        pearson    : Pearson correlation coefficient
        note       : optional descriptive note (non-gating)
    """

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
    weak_abs_threshold: float = 0.2,
) -> Optional[CouplingStat]:
    """
    Search lag window [-max_lag, +max_lag] for strongest Pearson coupling
    between source_col and target_col.

    Returns:
        CouplingStat or None if insufficient data.

    Tie-breaker logic (in order of precedence):
        1. Stronger absolute correlation (|pearson|)
        2. Larger sample size n (more statistical support)
        3. Lag closest to zero (least temporal displacement)
        4. If still tied → earliest lag in iteration order (deterministic)

    weak_abs_threshold:
        If best |pearson| < this value, note is set to "weak coupling".
        This is descriptive only (non-gating).
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

        candidate_abs = abs(pear)
        is_better = False

        if candidate_abs > best_abs:
            is_better = True
        elif candidate_abs == best_abs and best is not None:
            # Tie-breaker 1: larger sample size (more evidence)
            if n > best.n:
                is_better = True
            # Tie-breaker 2: lag closer to zero (least displacement)
            elif n == best.n and abs(lag) < abs(best.lag_days):
                is_better = True
            # Tie-breaker 3 (implicit):
            # earliest lag in iteration order (stable, deterministic)

        if is_better:
            best_abs = candidate_abs
            best = CouplingStat(
                col=source_col,
                lag_days=int(lag),
                n=int(n),
                pearson=float(pear),
                note="",
            )

    if best is None:
        return None

    if abs(best.pearson) < float(weak_abs_threshold):
        return CouplingStat(
            col=best.col,
            lag_days=best.lag_days,
            n=best.n,
            pearson=best.pearson,
            note="weak coupling",
        )

    return best
