#!/usr/bin/env python3
"""
DOMAIN → HYDRO INGRESS (SYSTEM)

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
from apps.psr_tools._latest_domain_wave import latest_wave

def main() -> None:
    waves = read_today()
    dw = latest_wave(waves, domain="system", channel="net_pressure")
    if not dw:
        print("ADAPTER: no latest system DomainWave")
        return

    emitted = 0

    for dw in waves:
        if dw.domain != "system":
            continue

        packet = HydroPacket(
            t=dw.t,
            packet_id=str(uuid.uuid4()),
            lane="system",
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
                "source": "psr.domain_to_system_ingress",
                "domain_wave_ts": dw.t,
                "extractor": dw.extractor,
            },

            rate=None,
            anomaly_flag=False,
            replay=False,

            # Rhythm coupling
            phase=dw.phase_diff,

            # NEW: explicit coherence transport
            coherence=dw.coherence,
        )

        decision = hydro_ingress_gate(packet)
        enqueue_if_admitted(packet, decision)
        emitted += 1

    print(f"SYSTEM INGRESS → emitted {emitted} packets")


if __name__ == "__main__":
    main()
