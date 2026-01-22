"""
Demo Synthetic Oscillator Observer (External)

Purpose:
- Prove end-to-end ingestion using Rhythm OS primitives
- No authority leakage
- Explicit persistence owned by caller
"""

import time
import math
import numpy as np
from pathlib import Path

from rhythm_os.adapters.observe.phase_extractor import extract_external_phase
from rhythm_os.domain.phase_compare import compute_domain_wave
from rhythm_os.domain.write import append_domain_wave
from rhythm_os.core.field import compute_field


# ---------------------------------------------------------
# Configuration (explicit, non-optimized)
# ---------------------------------------------------------

DOMAIN = "demo"
CHANNEL = "synthetic_sine"
FIELD_COMPONENT = "semi_diurnal"

PERIOD_S = 43200.0
OFFSET_DEG = 22.0
WINDOW_HOURS = 6
DT = 60.0

OUTPUT_PATH = Path(
    "data/demo/demo_sine.jsonl"   # OUTSIDE rhythm_os
)


# ---------------------------------------------------------
# Synthetic signal generator (physics-bound)
# ---------------------------------------------------------

def generate_sine_samples(t_now: float):
    offset_rad = math.radians(OFFSET_DEG)

    times = np.arange(
        t_now - WINDOW_HOURS * 3600,
        t_now + DT,
        DT
    )

    values = np.sin(
        2.0 * math.pi * (times - t_now) / PERIOD_S + offset_rad
    )

    return list(zip(times.tolist(), values.tolist()))


# ---------------------------------------------------------
# Main proof
# ---------------------------------------------------------

if __name__ == "__main__":
    t_now = time.time()

    samples = generate_sine_samples(t_now)

    phase_external, extractor_meta = extract_external_phase(
        samples,
        method="hilbert",
    )

    extractor_meta = {
        **extractor_meta,
        "synthetic_period_s": PERIOD_S,
        "intentional_offset_deg": OFFSET_DEG,
        "window_hours": WINDOW_HOURS,
    }

    # PURE domain computation
    wave = compute_domain_wave(
        t=t_now,
        domain=DOMAIN,
        channel=CHANNEL,
        phase_external=phase_external,
        field_component=FIELD_COMPONENT,
        coherence=1.0,
        extractor_meta=extractor_meta,
    )

    # EXPLICIT persistence (external authority)
    append_domain_wave(OUTPUT_PATH, wave)

    field = compute_field(t_now)

    print("\n— DOMAIN WAVE PERSISTED (EXTERNAL) —")
    print(wave)

    print("\nProof complete.")
    print(
        "Expected Δϕ ≈ +{:.1f}° (wrapped).".format(OFFSET_DEG)
    )

