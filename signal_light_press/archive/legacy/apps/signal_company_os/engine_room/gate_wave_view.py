"""
GateWaveView

READ-ONLY.
NO COMPUTATION.
NO INTERPRETATION.

A minimal view object that allows Signal Scope to render
already-computed gate diagnostics (e.g., r, v) without
introducing authority.

This is NOT a kernel Wave. It is a presentation-only view.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GateWaveView:
    # addressed timestamp (from envelope)
    t: float

    # coherence channel = already computed r (or any other [0,1] scalar you want to render)
    coherence: float

    # required by WaveView contract, but NOT meaningful here
    phase_spread: float = 0.0
    buffer_margin: float = 1.0
    persistence: int = 0

    # optional: allow scope to render something else without semantics
    drift: Optional[float] = None        # can be v, factor, etc. (already computed)
    afterglow: Optional[float] = None    # unused by default
