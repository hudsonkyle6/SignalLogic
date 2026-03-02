"""
Demo Synthetic Oscillator Observer (Canonical)

Purpose:
- Prove end-to-end ingestion without authority leakage
- Use ONLY locked primitives
- Produce ONE DomainWave
"""

import time
import math

try:
    import numpy as np
except ImportError as _e:
    raise ImportError(
        "numpy is required for the demo sine observer. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e
from pathlib import Path

from rhythm_os.adapters.observe.phase_extractor import extract_external_phase
from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.core.field import compute_field


# ---------------------------------------------------------
# Configuration (explicit, non-optimized)
# ---------------------------------------------------------

DOMAIN = "demo"
CHANNEL = "synthetic_sine"
FIELD_COMPONENT = "semi_diurnal"

PERIOD_S = 43200.0  # canonical semi-diurnal
OFFSET_DEG = 22.0  # intentional, controlled offset
WINDOW_HOURS = 6  # short causal window
DT = 60.0  # 60-second sampling

OUTPUT_PATH = Path("rhythm_os/domain/demo/waves/demo_sine.jsonl")


# ---------------------------------------------------------
# Synthetic signal generator
# ---------------------------------------------------------


def generate_sine_samples(t_now: float):
    offset_rad = math.radians(OFFSET_DEG)

    times = np.arange(t_now - WINDOW_HOURS * 3600, t_now + DT, DT)

    values = np.sin(2.0 * math.pi * (times - t_now) / PERIOD_S + offset_rad)

    return list(zip(times.tolist(), values.tolist()))


# ---------------------------------------------------------
# Main proof
# ---------------------------------------------------------

if __name__ == "__main__":
    t_now = time.time()

    # 1. Generate synthetic samples
    samples = generate_sine_samples(t_now)

    # 2. Extract external phase (HILBERT — canonical)
    phase_external, extractor_meta = extract_external_phase(
        samples,
        method="hilbert",
    )

    # Annotate metadata (allowed)
    extractor_meta = {
        **extractor_meta,
        "synthetic_period_s": str(PERIOD_S),
        "intentional_offset_deg": str(OFFSET_DEG),
        "window_hours": str(WINDOW_HOURS),
    }

    # 3. Build DomainWave (single write)
    phase_field = 0.0  # synthetic reference phase (explicit, non-optimized)

    wave = DomainWave(
        t=t_now,
        domain=DOMAIN,
        channel=CHANNEL,
        field_cycle=FIELD_COMPONENT,
        phase_external=phase_external,
        phase_field=phase_field,
        phase_diff=(phase_external - phase_field),
        coherence=1.0,
        extractor="demo_sine_observer",
    )

    # 4. Render report with this DomainWave
    field = compute_field(t_now)

    print("\n— DOMAIN WAVE WRITTEN —")
    print(wave)
    print("\nField sample:")
    print(field)

    print("\nProof complete.")
    print(
        "Expected Δϕ ≈ +{:.1f}° (wrapped), subject to small numerical noise.".format(
            OFFSET_DEG
        )
    )
