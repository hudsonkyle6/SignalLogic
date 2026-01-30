"""
SIGNAL_SCOPE_V2 — Observational Renderer

This file is an implementation of the declarative instrument defined in:
SIGNAL_SCOPE_V2.md

The markdown specification is authoritative.
This code exists only to render what has already been observed.
"""


from __future__ import annotations

from typing import Iterable, Protocol, Optional
import math


# ---------------------------------------------------------------------
# Read-only Wave View Contract
# ---------------------------------------------------------------------
class WaveView(Protocol):
    """
    Minimal, read-only view into a sealed Wave.
    The scope may only render what already exists.
    """

    t: float                     # timestamp (addressed, not owned)
    coherence: float             # [0, 1]
    phase_spread: float          # radians
    buffer_margin: float         # [0, 1] where 0 = at envelope edge
    persistence: int             # recurrence count (non-negative)

    # Optional (render only if present)
    drift: Optional[float]       # signed, unitless
    afterglow: Optional[float]   # [0, 1]


# ---------------------------------------------------------------------
# Rendering Helpers (Pure Presentation)
# ---------------------------------------------------------------------
def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _bar(value: float, width: int = 48) -> str:
    """
    Render a horizontal bar without semantics.
    """
    v = _clamp01(value)
    filled = int(v * width)
    return "█" * filled + " " * (width - filled)


def _label(title: str) -> None:
    print("\n" + title)
    print("─" * len(title))


# ---------------------------------------------------------------------
# Passive Oscilloscope
# ---------------------------------------------------------------------
def render_scope(
    waves: Iterable[WaveView],
    *,
    window: int = 120,
) -> None:
    """
    Passive oscilloscope.

    - Accepts an iterable of sealed Wave objects (or views).
    - Applies windowing by omission only.
    - Produces no inference, state, or authority.
    """

    waves = list(waves)[-window:]

    print("\n" + "═" * 80)
    print("   RHYTHM OS — SIGNAL SCOPE (OBSERVATION ONLY)")
    print("═" * 80)

    if not waves:
        print("   (no waves in window)")
        print("═" * 80 + "\n")
        return

    # ---------------------------------------------------------------
    # COHERENCE TRACE
    # ---------------------------------------------------------------
    _label("COHERENCE")
    for w in waves:
        print(_bar(_clamp01(w.coherence)))

    # ---------------------------------------------------------------
    # PHASE SPREAD TRACE (normalized to π)
    # ---------------------------------------------------------------
    _label("PHASE SPREAD")
    for w in waves:
        norm = min(1.0, abs(float(w.phase_spread)) / math.pi)
        print(_bar(norm))

    # ---------------------------------------------------------------
    # BUFFER PROXIMITY TRACE (1 - margin)
    # ---------------------------------------------------------------
    _label("BUFFER PROXIMITY")
    for w in waves:
        proximity = 1.0 - _clamp01(w.buffer_margin)
        print(_bar(proximity))

    # ---------------------------------------------------------------
    # PERSISTENCE TRACE (relative within window)
    # ---------------------------------------------------------------
    _label("PERSISTENCE")
    max_p = max((int(w.persistence) for w in waves), default=1)
    max_p = max(max_p, 1)
    for w in waves:
        print(_bar(int(w.persistence) / max_p))

    # ---------------------------------------------------------------
    # OPTIONAL TRACES (ONLY IF PRESENT)
    # ---------------------------------------------------------------
    if any(getattr(w, "drift", None) is not None for w in waves):
        _label("DRIFT (ABSOLUTE)")
        max_d = max((abs(float(w.drift)) for w in waves if w.drift is not None), default=1.0)
        max_d = max(max_d, 1e-9)
        for w in waves:
            d = abs(float(w.drift)) if w.drift is not None else 0.0
            print(_bar(min(1.0, d / max_d)))

    if any(getattr(w, "afterglow", None) is not None for w in waves):
        _label("AFTERGLOW")
        for w in waves:
            a = _clamp01(w.afterglow) if w.afterglow is not None else 0.0
            print(_bar(a))

    print("═" * 80 + "\n")


# ---------------------------------------------------------------------
# Explicit Prohibitions (Documentation Guardrail)
# ---------------------------------------------------------------------
# This module MUST NEVER:
# - contain a scheduler or loop
# - import observation, oracle, sage, shepherd, or execution code
# - compute signals or phases
# - name regimes or postures
# - imply action or timing
#
# Any violation collapses this instrument back to silence.
