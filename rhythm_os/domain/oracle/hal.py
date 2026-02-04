#hal.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

TAU = 2.0 * math.pi


def wrap_phase_rad(delta: float) -> float:
    """
    Wrap a phase delta into [-pi, pi].

    Pure geometry.
    No thresholds.
    No interpretation.
    """
    d = (float(delta) + math.pi) % TAU - math.pi
    return d


def rad_to_deg(rad: float) -> float:
    """
    Convenience conversion for readability only.
    """
    return math.degrees(float(rad))


@dataclass(frozen=True)
class HALMeasurement:
    """
    Harmonic Alignment Law (HAL) measurement record.

    Measurement only.
    Grants no authority.
    """
    phase_diff_rad: float                 # wrapped [-pi, pi]
    phase_diff_deg: float                 # wrapped [-180, 180]
    coherence_proxy: Optional[float] = None


def measure_alignment(
    *,
    phase_external_rad: float,
    phase_field_rad: float,
    coherence_proxy: Optional[float] = None,
) -> HALMeasurement:
    """
    Compute descriptive alignment quantities:

    Δϕ = ϕ_h - ϕ_e  (wrapped)
    plus optional coherence proxy.

    This function must never:
    - bucket
    - threshold
    - recommend
    - authorize
    """
    raw = float(phase_external_rad) - float(phase_field_rad)
    wrapped = wrap_phase_rad(raw)
    return HALMeasurement(
        phase_diff_rad=wrapped,
        phase_diff_deg=rad_to_deg(wrapped),
        coherence_proxy=float(coherence_proxy) if coherence_proxy is not None else None,
    )
