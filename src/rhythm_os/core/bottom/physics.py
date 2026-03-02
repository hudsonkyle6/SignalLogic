"""
BOTTOM LAYER — PHYSICS ONLY

This module is frozen by charter.

FORBIDDEN:
- APIs
- Sensors
- Files
- Pandas
- Historical lookup
- Backfilling
- Human input
- Market data
- Optimization
- Prediction
- Interpretation

This module computes deterministic physical cycles only.
"""

"""
BOTTOM LAYER — PHYSICS ONLY (FROZEN)

Deterministic oscillatory field.
Pure time → pure invariants.

FORBIDDEN:
- APIs
- Sensors
- Files
- Pandas
- Historical lookup
- Backfilling
- Human input
- Market data
- Optimization
- Prediction
- Interpretation
"""

import math
import cmath
from dataclasses import dataclass
from typing import Optional, Dict


# ---------------------------------------------------------------------
# Canonical periods (seconds) — FROZEN
# ---------------------------------------------------------------------

T_DIURNAL = 86400.0
T_SEMI_DIURNAL = 43200.0
T_SEASONAL = 365.2422 * 86400.0
T_LONGWAVE = 18.61 * T_SEASONAL

CYCLES = {
    "diurnal": T_DIURNAL,
    "semi_diurnal": T_SEMI_DIURNAL,
    "seasonal": T_SEASONAL,
    "longwave": T_LONGWAVE,
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

TAU = 2.0 * math.pi


def wrap_angle(theta: float) -> float:
    """Wrap angle to (-pi, pi]."""
    while theta <= -math.pi:
        theta += TAU
    while theta > math.pi:
        theta -= TAU
    return theta


# ---------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class CycleState:
    period: float
    omega: float
    phase: float
    sine: float
    amplitude: float
    phasor: complex


@dataclass(frozen=True)
class OscillatoryField:
    t: float
    cycles: Dict[str, CycleState]
    composite_phasor: complex
    composite_phase: float
    coherence: float
    coherence_drift: Optional[float] = None
    phase_drift: Optional[float] = None


# ---------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------


def compute_field(t: float, t_prev: Optional[float] = None) -> OscillatoryField:
    cycles: Dict[str, CycleState] = {}
    phasors = []

    for name, T in CYCLES.items():
        omega = TAU / T
        phase = (omega * t) % TAU
        s = math.sin(phase)
        a = 0.5 * (1.0 + s)
        z = cmath.exp(1j * phase)

        cycles[name] = CycleState(
            period=T,
            omega=omega,
            phase=phase,
            sine=s,
            amplitude=a,
            phasor=z,
        )
        phasors.append(z)

    Z = sum(phasors)
    N = len(phasors)

    composite_phase = cmath.phase(Z)
    coherence = abs(Z) / N

    coherence_drift = None
    phase_drift = None

    if t_prev is not None and t_prev != t:
        prev = compute_field(t_prev)
        dt = t - t_prev
        coherence_drift = (coherence - prev.coherence) / dt
        phase_drift = wrap_angle(composite_phase - prev.composite_phase) / dt

    return OscillatoryField(
        t=t,
        cycles=cycles,
        composite_phasor=Z,
        composite_phase=composite_phase,
        coherence=coherence,
        coherence_drift=coherence_drift,
        phase_drift=phase_drift,
    )
