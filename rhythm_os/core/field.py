# rhythm_os/core/field.py

from dataclasses import dataclass
import math
import cmath
from typing import Dict

from rhythm_os.core.field_wave import FieldWave

# ---------------------------------------------------------------------
# Canonical oscillatory periods (seconds) — FROZEN
# ---------------------------------------------------------------------

CYCLES: Dict[str, float] = {
    "diurnal": 86400.0,
    "semi_diurnal": 43200.0,
    "seasonal": 365.2422 * 86400.0,
    "longwave": 18.61 * 365.2422 * 86400.0,
}

TAU = 2.0 * math.pi

# ---------------------------------------------------------------------
# Immutable Field Sample (Observatory-facing)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSample:
    t: float                          # UTC timestamp (seconds)
    phases: Dict[str, float]          # radians [0, 2π)
    phasors: Dict[str, complex]       # e^{jϕ}
    composite: complex                # Σ phasors
    coherence: float                  # |Σ| / N
    reference_phase: float            # atan2(Im(Σ), Re(Σ)) — derived, safe


# ---------------------------------------------------------------------
# Core computation — PURE PHYSICS
# ---------------------------------------------------------------------

def _phase(t: float, T: float) -> float:
    """Phase in radians for period T at time t."""
    return (TAU * (t / T)) % TAU


def compute_field(t: float) -> FieldSample:
    """
    Compute the sovereign oscillatory field at time t.

    Rules:
    - Time only
    - Deterministic
    - No I/O
    - No semantics
    - No interpretation
    """

    phases: Dict[str, float] = {}
    phasors: Dict[str, complex] = {}

    for name, T in CYCLES.items():
        phi = _phase(t, T)
        phases[name] = phi
        phasors[name] = cmath.exp(1j * phi)

    composite = sum(phasors.values())
    N = len(phasors)
    coherence = abs(composite) / N if N > 0 else 0.0

    reference_phase = math.atan2(
        composite.imag,
        composite.real,
    )

    return FieldSample(
        t=t,
        phases=phases,
        phasors=phasors,
        composite=composite,
        coherence=coherence,
        reference_phase=reference_phase,
    )


# ---------------------------------------------------------------------
# Field → Wave Materialization (Read-only)
# ---------------------------------------------------------------------

def materialize_field_waves(field: FieldSample) -> Dict[str, FieldWave]:
    """
    Materialize sovereign reference waves from FieldSample.

    Read-only.
    No authority.
    No side effects.
    """

    waves: Dict[str, FieldWave] = {}

    for name, phase in field.phases.items():
        phasor = field.phasors[name]
        sine = math.sin(phase)

        waves[name] = FieldWave(
            t=field.t,
            cycle=name,
            phase=phase,
            sine=sine,
            phasor=phasor,
        )

    return waves
