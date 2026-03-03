#!/usr/bin/env python3
"""
DOMAIN → HYDRO INGRESS (CYBER ATTACK)

POSTURE:
- Adapter only
- Gate remains Hydro-owned
- No dispatch
- No commit

Reads DomainWaves with channel="attack_pressure" and enqueues them as
HydroPackets.  Sets anomaly_flag=True when the anomaly_score exceeds the
threshold — this routes the packet through SPILLWAY for second-look triage.
"""

from __future__ import annotations

import uuid

from rhythm_os.psr.read_domain_waves import read_today
from signal_core.core.hydro_types import HydroPacket
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_ingress_throat import enqueue_if_admitted
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)

# Packets with anomaly_score above this threshold get anomaly_flag=True
# and are routed to SPILLWAY for second-look assessment.
_ANOMALY_THRESHOLD = 0.30


def main() -> None:
    waves = read_today()
    if not waves:
        log.info("CYBER ATTACK ADAPTER: no DomainWaves today")
        return

    emitted = 0

    for dw in waves:
        if dw.domain != "cyber" or dw.channel != "attack_pressure":
            continue

        # Extract anomaly_score from extractor metadata
        anomaly_score = float(dw.extractor.get("anomaly_score", 0.0))
        scenario = dw.extractor.get("scenario", "unknown")
        is_anomaly = anomaly_score > _ANOMALY_THRESHOLD

        packet = HydroPacket(
            t=dw.t,
            packet_id=str(uuid.uuid4()),
            lane="cyber",
            domain=dw.domain,
            channel=dw.channel,
            value={
                "phase_external": dw.phase_external,
                "phase_field": dw.phase_field,
                "phase_diff": dw.phase_diff,
                "coherence": dw.coherence,
                "field_cycle": dw.field_cycle,
                "scenario": scenario,
                "anomaly_score": anomaly_score,
            },
            provenance={
                "source": "psr.domain_to_cyber_attack_ingress",
                "domain_wave_ts": dw.t,
                "extractor": dw.extractor,
            },
            rate=None,
            anomaly_flag=is_anomaly,
            replay=False,
            phase=dw.phase_diff,
            coherence=dw.coherence,
        )

        decision = hydro_ingress_gate(packet)
        enqueue_if_admitted(packet, decision)
        emitted += 1

        if is_anomaly:
            log.warning(
                "CYBER ATTACK: anomaly_flag=True scenario=%s score=%.3f",
                scenario,
                anomaly_score,
            )

    log.info("CYBER ATTACK INGRESS: emitted %d packets", emitted)


if __name__ == "__main__":
    configure()
    main()
