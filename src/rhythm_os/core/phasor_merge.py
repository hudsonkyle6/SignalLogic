# src/rhythm_os/core/phasor_merge.py
"""
PHASOR MERGE — PURE MATH (FROZEN)

Role:
- Project (t, amplitude) samples onto one or more clock periods
- Return per-clock phasor, coherence, and phase
- Return group-merged phasor/coherence/phase (equal-weight by default)

FORBIDDEN:
- Files
- Pandas
- Historical lookup
- Side effects
- Randomness
"""

from __future__ import annotations

import math
import cmath
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple, Optional

__all__ = [
    "ClockProjection",
    "GroupProjection",
    "project_samples_to_clocks",
    "wrap_angle",
]

TAU = 2.0 * math.pi


def wrap_angle(theta: float) -> float:
    """Wrap angle to (-pi, pi]."""
    while theta <= -math.pi:
        theta += TAU
    while theta > math.pi:
        theta -= TAU
    return theta


@dataclass(frozen=True)
class ClockProjection:
    period_s: float
    omega: float
    phasor: complex     # Z_k (normalized by mag_sum)
    coherence: float    # r_k = |Z_k|
    phase: float        # arg(Z_k)


@dataclass(frozen=True)
class GroupProjection:
    phasor: complex     # Z_group (equal-weight merge of Z_k)
    coherence: float    # r_group = |Z_group|
    phase: float        # arg(Z_group)
    clocks: Dict[str, ClockProjection]


def project_samples_to_clocks(
    samples: Iterable[Tuple[float, float]],
    clocks: Dict[str, float],
    *,
    min_mag_sum: float = 1e-12,
) -> GroupProjection:
    """
    Project samples onto each clock.

    samples: (t_seconds, amplitude) where amplitude >= 0 is recommended
    clocks:  {name: period_seconds}

    Math:
      Z_k_raw = Σ a_i * exp(j * ω_k * t_i)
      mag_sum = Σ |a_i|
      Z_k = Z_k_raw / mag_sum
      r_k = |Z_k|

      Z_group = (1/N) Σ Z_k
      r_group = |Z_group|
    """
    items: List[Tuple[float, float]] = []
    for t, a in samples:
        try:
            items.append((float(t), float(a)))
        except Exception:
            continue

    if not items:
        # Pure silence
        return GroupProjection(
            phasor=0j,
            coherence=0.0,
            phase=0.0,
            clocks={},
        )

    mag_sum = 0.0
    for _, a in items:
        mag_sum += abs(a)

    if mag_sum < min_mag_sum or not clocks:
        return GroupProjection(
            phasor=0j,
            coherence=0.0,
            phase=0.0,
            clocks={},
        )

    clock_out: Dict[str, ClockProjection] = {}
    Z_sum = 0j
    n = 0

    for name, T in clocks.items():
        T = float(T)
        if T <= 0:
            continue
        omega = TAU / T

        Z_raw = 0j
        for t, a in items:
            Z_raw += a * cmath.exp(1j * (omega * t))

        Z = Z_raw / mag_sum
        r = abs(Z)
        phi = cmath.phase(Z) if r > 0 else 0.0

        cp = ClockProjection(
            period_s=T,
            omega=omega,
            phasor=Z,
            coherence=r,
            phase=phi,
        )
        clock_out[name] = cp
        Z_sum += Z
        n += 1

    if n == 0:
        return GroupProjection(
            phasor=0j,
            coherence=0.0,
            phase=0.0,
            clocks={},
        )

    Z_group = Z_sum / float(n)
    r_group = abs(Z_group)
    phi_group = cmath.phase(Z_group) if r_group > 0 else 0.0

    return GroupProjection(
        phasor=Z_group,
        coherence=r_group,
        phase=phi_group,
        clocks=clock_out,
    )
