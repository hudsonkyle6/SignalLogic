#!/usr/bin/env python3
"""
PSR — Observe System (Network Meters)

POSTURE: PSR (observation → domain)
"""

from __future__ import annotations

import json
from statistics import mean, pstdev
from typing import List, Dict, Any

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.runtime.bus import today_bus_file


# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

from rhythm_os.runtime.paths import METERS_DIR, PSR_DIR
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)

LANE = "net"
DOMAIN = "system"
CHANNEL = "net_flow"
FIELD_CYCLE = "windowed_flow"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def read_today_meter_packets() -> List[Dict[str, Any]]:
    if not METERS_DIR.exists():
        return []

    files = sorted(METERS_DIR.glob("*.jsonl"))
    if not files:
        return []

    packets: List[Dict[str, Any]] = []
    with files[-1].open("r", encoding="utf-8") as f:
        for line in f:
            pkt = json.loads(line)
            if pkt.get("lane") == LANE:
                packets.append(pkt)

    return packets


def compute_pressure(pkts: List[Dict[str, Any]]) -> Dict[str, float]:
    in_rates = [p["data"]["in_rate_bps"] for p in pkts]
    out_rates = [p["data"]["out_rate_bps"] for p in pkts]
    turb = [p["data"]["turbidity_out"] for p in pkts]

    return {
        "phase_external": mean(out_rates),
        "phase_field": mean(in_rates),
        "phase_diff": mean(out_rates) - mean(in_rates),
        "coherence": 1.0 / (1.0 + pstdev(turb)) if len(turb) > 1 else 1.0,
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    packets = read_today_meter_packets()
    if not packets:
        log.info("SYSTEM NET OBSERVE: no meter packets")
        return

    pressure = compute_pressure(packets)
    t = packets[-1]["t"]

    dw = DomainWave(
        t=t,
        domain=DOMAIN,
        channel=CHANNEL,
        field_cycle=FIELD_CYCLE,
        phase_external=pressure["phase_external"],
        phase_field=pressure["phase_field"],
        phase_diff=pressure["phase_diff"],
        coherence=pressure["coherence"],
        extractor={
            "source": "observe_system_from_net_meters",
            "instrument": "hydro_meter.net",
            "version": "v1",
        },
    )

    out_path = today_bus_file(bus_dir=PSR_DIR, t_ref=t)
    append_domain_wave(out_path, dw)

    log.info(
        "SYSTEM NET OBSERVED out_bps=%.1f imbalance=%.1f coherence=%.3f",
        pressure["phase_external"],
        pressure["phase_diff"],
        pressure["coherence"],
    )


if __name__ == "__main__":
    configure()
    main()
