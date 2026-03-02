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
    phase: float
    amplitude: float
    afterglow_decay: float
    # optional convenience fields if adapters provide them
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

    # -------------------------------------------------------------
    # COHERENCE (CARRIER = Wave.amplitude)
    # -------------------------------------------------------------
    _label("COHERENCE (PHASE-LOCK CARRIER: amplitude 0–1)")
    for w in waves:
        print(_bar(_clamp01(getattr(w, "amplitude", 0.0))))

    # -------------------------------------------------------------
    # PHASE SPREAD (if provided by adapter)
    # -------------------------------------------------------------
    _label("PHASE SPREAD")
    for w in waves:
        ps = float(getattr(w, "phase_spread", 0.0))
        norm = min(1.0, abs(ps) / math.pi)
        print(_bar(norm))

    # -------------------------------------------------------------
    # BUFFER PROXIMITY (if provided by adapter)
    # -------------------------------------------------------------
    _label("BUFFER PROXIMITY")
    for w in waves:
        bm = float(getattr(w, "buffer_margin", 1.0))
        proximity = 1.0 - _clamp01(bm)
        print(_bar(proximity))

    # -------------------------------------------------------------
    # PERSISTENCE (if provided by adapter)
    # -------------------------------------------------------------
    _label("PERSISTENCE")
    max_p = max((int(getattr(w, "persistence", 0)) for w in waves), default=1)
    max_p = max(max_p, 1)
    for w in waves:
        p = int(getattr(w, "persistence", 0))
        print(_bar(p / max_p))

    # -------------------------------------------------------------
    # AFTERGLOW (if provided by adapter)
    # -------------------------------------------------------------
    if any(getattr(w, "afterglow", None) is not None for w in waves):
        _label("AFTERGLOW")
        for w in waves:
            a = getattr(w, "afterglow", None)
            a_val = _clamp01(float(a)) if a is not None else 0.0
            print(_bar(a_val))

    print("═" * 80 + "\n")
