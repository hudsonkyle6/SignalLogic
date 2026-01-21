from dataclasses import dataclass
import math
import cmath
from typing import Dict
from rhythm_os.core.field_wave import FieldWave
# ---------------------------------------------------------------------
# Canonical oscillatory periods (seconds)
# ---------------------------------------------------------------------

CYCLES: Dict[str, float] = {
    "diurnal": 86400.0,
    "semi_diurnal": 43200.0,
    "seasonal": 365.2422 * 86400.0,
    "longwave": 18.61 * 365.2422 * 86400.0,
}

# ---------------------------------------------------------------------
# Immutable Field Sample
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSample:
    t: float                          # UTC timestamp (seconds)
    phases: Dict[str, float]          # radians [0, 2π)
    phasors: Dict[str, complex]       # e^{jϕ}
    composite: complex                # Σ phasors
    coherence: float                  # |Σ| / N

# ---------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------

def _phase(t: float, T: float) -> float:
    """Phase in radians for period T at time t."""
    return (2.0 * math.pi * (t / T)) % (2.0 * math.pi)

def compute_field(t: float) -> FieldSample:
    """
    Compute the sovereign oscillatory field at time t.
    No external inputs. No memory. No semantics.
    """
    phases = {}
    phasors = {}

    for name, T in CYCLES.items():
        phi = _phase(t, T)
        phases[name] = phi
        phasors[name] = cmath.exp(1j * phi)

    composite = sum(phasors.values())
    N = len(phasors)
    coherence = abs(composite) / N if N > 0 else 0.0

    return FieldSample(
        t=t,
        phases=phases,
        phasors=phasors,
        composite=composite,
        coherence=coherence,
    )


# rhythm_os/core/field.py

from rhythm_os.core.field_wave import FieldWave
import math

def materialize_field_waves(field) -> Dict[str, FieldWave]:
    """
    Materialize sovereign reference waves from FieldSample.
    Read-only. No authority.
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
