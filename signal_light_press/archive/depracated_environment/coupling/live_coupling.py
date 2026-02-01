# rhythm_os/core/coupling/live_coupling.py
"""
Live Coupling Wrapper — Real-Time Context

Delegates all math to canonical coupling engine.
Responsible only for:
    • window selection
    • current-state interpretation
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from rhythm_os.core.coupling.coupling import (
    CouplingStat,
    compute_coupling,
)


# ======================================================================
# RESULT STRUCTURE
# ======================================================================

@dataclass(frozen=True)
class LiveCouplingResult:
    resonance: Optional[CouplingStat]
    amplitude: Optional[CouplingStat]


# ======================================================================
# LIVE COUPLING
# ======================================================================

def compute_live_coupling(
    df: pd.DataFrame,
    window_days: int = 30,
    candidates: tuple[str, ...] = ("TempAvg", "MoonIllum"),
) -> LiveCouplingResult:
    """
    Compute current best coupling using recent window.
    """

    if "ResonanceValue" not in df.columns or "Amplitude" not in df.columns:
        return LiveCouplingResult(None, None)

    recent = df.tail(window_days)

    best_res = None
    best_amp = None
    best_res_abs = -1.0
    best_amp_abs = -1.0

    for col in candidates:
        if col not in recent.columns:
            continue

        # Resonance coupling
        res_stat = compute_coupling(
            df=recent,
            source_col=col,
            target_col="ResonanceValue",
            max_lag=7,
        )
        if res_stat and abs(res_stat.pearson) > best_res_abs:
            best_res_abs = abs(res_stat.pearson)
            best_res = res_stat

        # Amplitude coupling
        amp_stat = compute_coupling(
            df=recent,
            source_col=col,
            target_col="Amplitude",
            max_lag=30,
        )
        if amp_stat and abs(amp_stat.pearson) > best_amp_abs:
            best_amp_abs = abs(amp_stat.pearson)
            best_amp = amp_stat

    return LiveCouplingResult(
        resonance=best_res,
        amplitude=best_amp,
    )

