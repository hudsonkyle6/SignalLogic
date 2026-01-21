# rhythm_os/domain/oracle/demo_oracle.py
from __future__ import annotations

import time
from pathlib import Path

from rhythm_os.core.field import compute_field
from rhythm_os.domain.oracle.load import load_domain_waves_jsonl
from rhythm_os.domain.oracle.oracle import (
    describe_alignment,
    summarize_convergence,
)

DOMAIN_WAVES_PATH = Path("rhythm_os/domain/demo/waves/demo_sine.jsonl")
FIELD_CYCLE = "semi_diurnal"

if __name__ == "__main__":
    t_now = time.time()
    field = compute_field(t_now)

    domain_waves = load_domain_waves_jsonl(DOMAIN_WAVES_PATH)

    descriptors = describe_alignment(
        t_ref=field.t,
        field_cycle=FIELD_CYCLE,
        domain_waves=domain_waves,
    )

    summary = summarize_convergence(
        t_ref=field.t,
        descriptors=descriptors,
    )

    print("\n— ORACLE DESCRIPTORS —")
    for d in descriptors:
        print(d)

    print("\n— ORACLE CONVERGENCE —")
    print(summary)
