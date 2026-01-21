"""
Demo Synthetic Oscillator Observer (Canonical)

Purpose:
- Prove end-to-end ingestion without authority leakage
- Use ONLY locked primitives
- Produce ONE DomainWave
"""

import time
import math
import numpy as np
from pathlib import Path

from rhythm_os.adapters.observe.phase_extractor import extract_external_phase
from rhythm_os.adapters.observe.phase_compare import build_domain_wave
from rhythm_os.reports.signal_dashboard import render_signal_report
from rhythm_os.core.field import compute_field


# ---------------------------------------------------------
# Configuration (explicit, non-optimized)
# ---------------------------------------------------------

DOMAIN = "demo"
CHANNEL = "synthetic_sine"
FIELD_COMPONENT = "semi_diurnal"

PERIOD_S = 43200.0          # canonical semi-diurnal
OFFSET_DEG = 22.0           # intentional, controlled offset
WINDOW_HOURS = 6            # short causal window
DT = 60.0                   # 60-second sampling

OUTPUT_PATH = Path(
    "rhythm_os/domain/demo/waves/demo_sine.jsonl"
)


# ---------------------------------------------------------
# Synthetic signal generator
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
    wave = build_domain_wave(
        t=t_now,
        domain=DOMAIN,
        channel=CHANNEL,
        phase_external=phase_external,
        field_component=FIELD_COMPONENT,
        coherence=1.0,  # clean synthetic oscillator
        extractor_meta=extractor_meta,
        output_path=OUTPUT_PATH,
    )

    # 4. Render report with this DomainWave
    field = compute_field(t_now)

    print("\n— DOMAIN WAVE WRITTEN —")
    print(wave)

    render_signal_report(
        field_sample=field,
        domain_waves=[wave],
        engine_state={"posture": "SILENT", "state": "Still"},
        context={"season": "Reflect"},
    )

    print("\nProof complete.")
    print(
        "Expected Δϕ ≈ +{:.1f}° (wrapped), subject to small numerical noise.".format(
            OFFSET_DEG
        )
    )
