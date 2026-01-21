import math
from pathlib import Path
from typing import Optional

from rhythm_os.core.field import compute_field
from rhythm_os.domain.domain_wave import DomainWave
from rhythm_os.domain.write import append_domain_wave


# ---------------------------------------------------------
# Phase wrapping (canonical)
# ---------------------------------------------------------

def wrap_phase(delta: float) -> float:
    """
    Wrap phase difference into [-π, π].
    """
    return (delta + math.pi) % (2.0 * math.pi) - math.pi


# ---------------------------------------------------------
# DomainWave assembly
# ---------------------------------------------------------

def build_domain_wave(
    *,
    t: float,
    domain: str,
    channel: str,
    phase_external: float,
    field_component: str,
    coherence: Optional[float],
    extractor_meta: dict,
    output_path: Path,
) -> DomainWave:
    """
    Compare external phase to sovereign field and append DomainWave.
    """

    field = compute_field(t)

    if field_component not in field.phases:
        raise ValueError(
            f"Unknown field component '{field_component}'. "
            f"Available: {list(field.phases.keys())}"
        )

    phase_field = field.phases[field_component]
    phase_diff = wrap_phase(phase_external - phase_field)

    wave = DomainWave(
        t=t,
        domain=domain,
        channel=channel,
        phase_external=phase_external,
        phase_field=phase_field,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor=extractor_meta,
    )

    append_domain_wave(output_path, wave)
    return wave
