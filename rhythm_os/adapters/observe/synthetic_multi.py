from __future__ import annotations

import math
import time
from typing import List
from dataclasses import dataclass

import numpy as np
from scipy.signal import hilbert

from rhythm_os.core.field import compute_field
from rhythm_os.domain.domain_wave import DomainWave


TAU = 2 * math.pi

PERIODS = {
    "semi_diurnal": 43200.0,
}


@dataclass(frozen=True)
class SyntheticChannelSpec:
    name: str
    phase_offset_deg: float
    noise_std: float = 0.0


def _extract_phase(signal: np.ndarray) -> float:
    """
    Extract terminal phase of a signal via analytic signal.
    Descriptive only.
    """
    analytic = hilbert(signal)
    phase = np.unwrap(np.angle(analytic))
    return float(phase[-1] % TAU)


def generate_multi_channel_synthetic(
    *,
    t_now: float,
    cycle: str = "semi_diurnal",
    window_hours: float = 6.0,
    step_seconds: float = 60.0,
    channels: List[SyntheticChannelSpec],
) -> List[DomainWave]:
    """
    Generate multiple independent synthetic oscillators.

    - No coordination
    - No semantics
    - No authority
    """

    period = PERIODS[cycle]

    # Sovereign field (physics only)
    field = compute_field(t_now)
    field_phase = field.phases[cycle]


    # Time window
    t_series = np.arange(
        t_now - window_hours * 3600,
        t_now + step_seconds,
        step_seconds,
    )

    waves: List[DomainWave] = []

    for ch in channels:
        offset_rad = math.radians(ch.phase_offset_deg)

        signal = np.sin(
            TAU * (t_series / period) + offset_rad
        )

        if ch.noise_std > 0:
            signal += np.random.normal(0, ch.noise_std, size=len(signal))

        phase_ext = _extract_phase(signal)

        phase_diff = ((phase_ext - field_phase + math.pi) % TAU) - math.pi

        waves.append(
            DomainWave(
                t=t_now,
                domain="synthetic",
                channel=ch.name,
                field_cycle=cycle,
                phase_external=phase_ext,
                phase_field=field_phase,
                phase_diff=phase_diff,
                coherence=(
                    1.0
                    if ch.noise_std == 0
                    else max(0.0, 1.0 - ch.noise_std)
                ),
                extractor={
                    "type": "synthetic_multi",
                    "field_cycle": cycle,  # informational only
                    "period_s": period,
                    "offset_deg": ch.phase_offset_deg,
                    "noise_std": ch.noise_std,
                    "window_hours": window_hours,
                },
            )
        )

    return waves
