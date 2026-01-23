"""
Wave → WaveView Adapter + Signal Scope (ASCII)

READ-ONLY.
OBSERVATION-ONLY.

FORBIDDEN:
- Time ownership
- File I/O
- Signal computation
- Oracle / Sage / Shepherd logic
- Thresholding
- Decisions
- Narrative synthesis
- Execution hints

ALLOWED:
- Rendering sealed Wave objects
- Windowing by omission only
- Presentation-only decay (visual)

This module does not run the system.
It reflects observations already made.
"""

from __future__ import annotations
from typing import Iterable, Optional
import math


# ---------------------------------------------------------------------
# WaveView Adapter (Read-only contract)
# ---------------------------------------------------------------------
class WaveViewAdapter:
    """
    Uniform, read-only accessor over any wave-like object.

    The wrapped object must already contain computed fields.
    This adapter performs NO derivation or inference.
    """

    def __init__(self, wave: object):
        self._wave = wave

    @property
    def t(self) -> float:
        return float(getattr(self._wave, "t"))

    @property
    def coherence(self) -> float:
        return float(getattr(self._wave, "coherence"))

    @property
    def phase_spread(self) -> float:
        return float(getattr(self._wave, "phase_spread", 0.0))

    @property
    def buffer_margin(self) -> float:
        return float(getattr(self._wave, "buffer_margin", 1.0))

    @property
    def persistence(self) -> int:
        return int(getattr(self._wave, "persistence", 0))

    @property
    def drift(self) -> Optional[float]:
        return getattr(self._wave, "drift", None)

    @property
    def afterglow(self) -> Optional[float]:
        return getattr(self._wave, "afterglow", None)


# ---------------------------------------------------------------------
# Rendering helpers (pure presentation)
# ---------------------------------------------------------------------
def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _bar(value: float, width: int = 48) -> str:
    v = _clamp01(value)
    filled = int(v * width)
    return "█" * filled + " " * (width - filled)


def _label(title: str) -> None:
    print("\n" + title)
    print("─" * len(title))


# ---------------------------------------------------------------------
# ASCII Signal Scope
# ---------------------------------------------------------------------
def render_scope(
    waves: Iterable[object],
    *,
    window: int = 120,
) -> None:
    """
    Passive oscilloscope (ASCII).

    - Accepts wave-like objects
    - Adapts them via WaveViewAdapter
    - Applies windowing by omission only
    - Produces NO inference, state, or authority
    """

    adapters = [WaveViewAdapter(w) for w in waves][-window:]

    print("\n" + "═" * 80)
    print("   RHYTHM OS — SIGNAL SCOPE (OBSERVATION ONLY)")
    print("═" * 80)

    if not adapters:
        print("   (no waves in window)")
        print("═" * 80 + "\n")
        return

    # ---------------------------------------------------------------
    # COHERENCE
    # ---------------------------------------------------------------
    _label("COHERENCE")
    for a in adapters:
        print(_bar(a.coherence))

    # ---------------------------------------------------------------
    # PHASE SPREAD (normalized to π)
    # ---------------------------------------------------------------
    _label("PHASE SPREAD")
    for a in adapters:
        norm = min(1.0, abs(a.phase_spread) / math.pi)
        print(_bar(norm))

    # ---------------------------------------------------------------
    # BUFFER PROXIMITY (1 - margin)
    # ---------------------------------------------------------------
    _label("BUFFER PROXIMITY")
    for a in adapters:
        proximity = 1.0 - _clamp01(a.buffer_margin)
        print(_bar(proximity))

    # ---------------------------------------------------------------
    # PERSISTENCE (relative)
    # ---------------------------------------------------------------
    _label("PERSISTENCE")
    max_p = max((a.persistence for a in adapters), default=1)
    max_p = max(max_p, 1)
    for a in adapters:
        print(_bar(a.persistence / max_p))

    # ---------------------------------------------------------------
    # OPTIONAL: DRIFT
    # ---------------------------------------------------------------
    if any(a.drift is not None for a in adapters):
        _label("DRIFT (ABSOLUTE)")
        max_d = max(
            (abs(a.drift) for a in adapters if a.drift is not None),
            default=1.0,
        )
        max_d = max(max_d, 1e-9)
        for a in adapters:
            d = abs(a.drift) if a.drift is not None else 0.0
            print(_bar(min(1.0, d / max_d)))

    # ---------------------------------------------------------------
    # OPTIONAL: AFTERGLOW
    # ---------------------------------------------------------------
    if any(a.afterglow is not None for a in adapters):
        _label("AFTERGLOW")
        for a in adapters:
            print(_bar(_clamp01(a.afterglow) if a.afterglow is not None else 0.0))

    print("═" * 80 + "\n")


# ---------------------------------------------------------------------
# Guardrail
# ---------------------------------------------------------------------
# This module MUST NEVER:
# - import matplotlib or plotting libraries
# - write files
# - schedule execution
# - compute signals or phases
# - imply action or timing
#
# Any violation collapses this instrument back to silence.
