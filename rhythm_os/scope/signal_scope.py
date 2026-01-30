"""
Signal Scope — Oscillatory Diagnostic Instrument

READ-ONLY.
OBSERVATION-ONLY.

FORBIDDEN:
- Time ownership
- File I/O
- Signal computation
- Oracle logic
- Sage logic
- Shepherd logic
- Thresholding
- Decisions
- Narrative synthesis
- Execution hints

ALLOWED:
- Rendering sealed Wave objects
- Windowing (presentation only)
- Decay-by-omission (forgetting via window)

This module does not run the system.
It reflects observations already made.
"""

from __future__ import annotations

from typing import Iterable, Protocol, Optional
import math


class WaveView(Protocol):
    """
    Minimal, read-only view into a sealed Wave.
    The scope may only render what already exists.
    """
    t: float
    coherence: float
    phase_spread: float
    buffer_margin: float
    persistence: int

    drift: Optional[float]
    afterglow: Optional[float]


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _bar(value: float, width: int = 48) -> str:
    v = _clamp01(value)
    filled = int(v * width)
    return "█" * filled + " " * (width - filled)


def _label(title: str) -> None:
    print("\n" + title)
    print("─" * len(title))


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

    _label("COHERENCE")
    for w in waves:
        print(_bar(_clamp01(w.coherence)))

    _label("PHASE SPREAD")
    for w in waves:
        norm = min(1.0, abs(float(w.phase_spread)) / math.pi)
        print(_bar(norm))

    _label("BUFFER PROXIMITY")
    for w in waves:
        proximity = 1.0 - _clamp01(w.buffer_margin)
        print(_bar(proximity))

    _label("PERSISTENCE")
    max_p = max((int(w.persistence) for w in waves), default=1)
    max_p = max(max_p, 1)
    for w in waves:
        print(_bar(int(w.persistence) / max_p))

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


# EXPLICIT PROHIBITIONS:
# - no scheduler/loop
# - no imports of observation/oracle/sage/shepherd/execution
# - no computation/thresholding/decisions
