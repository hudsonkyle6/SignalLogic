#!/usr/bin/env python3
"""
DOMAIN → HYDRO INGRESS (CYBER)

POSTURE:
- Adapter only
- Gate remains Hydro-owned
- No dispatch
- No commit
"""

from __future__ import annotations

import uuid

from rhythm_os.psr.read_domain_waves import read_today
from signal_core.core.hydro_types import HydroPacket
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_ingress_throat import enqueue_if_admitted


def main() -> None:
    waves = read_today()
    if not waves:
        print("ADAPTER: no DomainWaves to emit")
        return

    emitted = 0

    for dw in waves:
        if dw.domain != "cyber":
            continue

        packet = HydroPacket(
            t=dw.t,
            packet_id=str(uuid.uuid4()),

            lane="cyber",
            domain=dw.domain,
            channel=dw.channel,

            # Observational payload (kept for trace)
            value={
                "phase_external": dw.phase_external,
                "phase_field": dw.phase_field,
                "phase_diff": dw.phase_diff,
                "coherence": dw.coherence,
                "field_cycle": dw.field_cycle,
            },

            provenance={
                "source": "psr.domain_to_cyber_ingress",
                "domain_wave_ts": dw.t,
                "extractor": dw.extractor,
            },

            rate=None,
            anomaly_flag=False,
            replay=False,

            # Rhythm coupling: use phase_diff as phase transport
            phase=dw.phase_diff,

            # Explicit coherence transport
            coherence=dw.coherence,
        )

        decision = hydro_ingress_gate(packet)
        enqueue_if_admitted(packet, decision)
        emitted += 1

    print(f"CYBER INGRESS → emitted {emitted} packets")


if __name__ == "__main__":
    main()
