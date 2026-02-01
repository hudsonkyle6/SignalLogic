# rhythm_os/core/coupling/lagged_coupling.py
"""
Lagged Coupling Wrapper — Historical / Backfill

Delegates all math to canonical coupling engine.
Adds:
    • window slicing
    • historical context
    • graceful degradation
"""

from __future__ import annotations
from typing import Iterable, Optional
import pandas as pd

from rhythm_os.core.coupling.coupling import (
    CouplingStat,
    compute_coupling,
)


def compute_lagged_coupling(
    window: pd.DataFrame,
    target_col: str = "Amplitude",
    natural_cols: Iterable[str] = ("TempAvg", "MoonIllum"),
    max_lag: int = 7,
    min_points: int = 7,
) -> Optional[CouplingStat]:
    """
    Evaluate historical lagged coupling across candidate natural columns.
    Returns strongest CouplingStat or None.
    """

    if target_col not in window.columns or len(window) < min_points:
        return None

    best: Optional[CouplingStat] = None
    best_abs = -1.0

    for col in natural_cols:
        if col not in window.columns:
            continue

        stat = compute_coupling(
            df=window,
            source_col=col,
            target_col=target_col,
            max_lag=max_lag,
            min_points=min_points,
        )

        if not stat:
            continue

        if abs(stat.pearson) > best_abs:
            best_abs = abs(stat.pearson)
            best = stat

    return best
