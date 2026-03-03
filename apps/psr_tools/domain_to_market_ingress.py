#!/usr/bin/env python3
"""
DOMAIN → HYDRO INGRESS (MARKET)

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
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)


def main() -> None:
    waves = read_today()
    if not waves:
        log.info("ADAPTER: no DomainWaves to emit")
        return

    emitted = 0

    for dw in waves:
        if dw.domain != "market":
            continue

        packet = HydroPacket(
            t=dw.t,
            packet_id=str(uuid.uuid4()),
            lane="market",
            domain=dw.domain,
            channel=dw.channel,
            value={
                "pressure": dw.phase_external,
                "coherence": dw.coherence,
                "field_cycle": dw.field_cycle,
            },
            provenance={
                "source": "psr.domain_to_market_ingress",
                "domain_wave_ts": dw.t,
                "extractor": dw.extractor,
            },
            rate=None,
            anomaly_flag=False,
            replay=False,
            phase=dw.phase_external,
        )

        decision = hydro_ingress_gate(packet)
        enqueue_if_admitted(packet, decision)
        emitted += 1

    log.info("MARKET INGRESS: emitted %d packets", emitted)


if __name__ == "__main__":
    configure()
    main()
