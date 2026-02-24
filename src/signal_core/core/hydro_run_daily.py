#!/usr/bin/env python3
"""
Signal Hydro — Daily Run
POSTURE: HYDRO (SOLE PENSTOCK AUTHORITY)

Consumes admitted ingress packets and commits
sealed Waves to the Dark Field (penstock).

This module:
- DOES drain the ingress queue
- DOES structurally re-gate
- DOES dispatch (routing only)
- DOES commit to penstock (MAIN ONLY)
- DOES witness successful dispatches (audit)
- DOES NOT fabricate packets
- DOES NOT call observatory cycles

See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

import json
from typing import List

from rhythm_os.core.wave.wave import Wave
from rhythm_os.core.dark_field.store import append_wave_from_hydro

from signal_core.core.hydro_types import HydroPacket, GateResult
from signal_core.core.hydro_ingress_queue import drain_queue
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_dispatcher import dispatch
from signal_core.core.hydro_audit import append_audit


# ---------------------------------------------------------------------
# Penstock commit
# ---------------------------------------------------------------------

def commit_packet(packet: HydroPacket) -> None:
    """
    Commit a single packet to the penstock as a sealed Wave.

    Packet coherence is mapped into Wave amplitude.
    No inference. No transformation beyond clamping.
    """

    # Extract coherence from packet payload (authoritative)
    try:
        amplitude = float((packet.value or {}).get("coherence", 0.0) or 0.0)
    except Exception:
        amplitude = 0.0

    # Clamp to [0,1]
    if amplitude < 0.0:
        amplitude = 0.0
    if amplitude > 1.0:
        amplitude = 1.0

    wave = Wave.create(
        text=json.dumps(
            packet.__dict__,
            sort_keys=True,
            separators=(",", ":"),
        ),
        signal_type=f"{packet.domain}::{packet.lane}::{packet.channel}",
        phase=float(getattr(packet, "phase", 0.0) or 0.0),
        frequency=1.0,
        amplitude=amplitude,  # coherence carrier
        afterglow_decay=0.5,
        couplings={},
    )

    append_wave_from_hydro(wave)



# ---------------------------------------------------------------------
# Main hydro cadence
# ---------------------------------------------------------------------

def main() -> None:
    """
    Daily hydro cadence.

    Sole responsibilities:
    - drain ingress queue
    - structurally re-gate
    - dispatch (route only)
    - commit MAIN waves
    - witness successful dispatches
    """

    packets: List[HydroPacket] = drain_queue()

    print(f"HYDRO: drained={len(packets)}")

    if not packets:
        return

    for packet in packets:
        ingress = hydro_ingress_gate(packet)
        print(f"INGRESS: {ingress.gate_result.value} {ingress.reason}")

        # -------------------------------------------------------------
        # D0 — REJECT
        # -------------------------------------------------------------
        if ingress.gate_result == GateResult.REJECT:
            continue

        decision = dispatch(packet, ingress)
        print(f"DISPATCH: {decision.route.value} {decision.rule_id}")

        # -------------------------------------------------------------
        # MAIN — sole penstock authority
        # -------------------------------------------------------------
        if decision.route.name == "MAIN":
            commit_packet(packet)
            append_audit(packet, ingress.gate_result.value, "MAIN")
            print("COMMIT: OK (MAIN)")
            continue

        # -------------------------------------------------------------
        # TURBINE — exploratory, non-penstock
        # -------------------------------------------------------------
        if decision.route.name == "TURBINE":
            append_audit(packet, ingress.gate_result.value, "TURBINE")
            print("COMMIT: SKIP (TURBINE)")
            continue

        # -------------------------------------------------------------
        # SPILLWAY / DROP
        # -------------------------------------------------------------
        print("COMMIT: SKIP (non-penstock route)")


if __name__ == "__main__":
    main()
