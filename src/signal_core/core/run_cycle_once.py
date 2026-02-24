#!/usr/bin/env python3
"""
Signal Core — Run Cycle Once
POSTURE: OBSERVATORY

Responsibilities:
- Observe one signal
- Apply hydro ingress gate (structural admission)
- Enqueue admitted packets (PASS | QUARANTINE)
- Perform dispatch for trace/logging only

This module:
- DOES NOT write penstock
- DOES NOT drain queues
- DOES NOT fabricate downstream state

See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from signal_core.core.hydro_types import HydroPacket, GateResult
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_ingress_throat import enqueue_if_admitted
from signal_core.core.hydro_dispatcher import dispatch


def observe_once() -> HydroPacket:
    """
    Produce a single observational packet.

    This is a bootstrap observer.
    Future observers will replace this.
    """
    return HydroPacket(
        t=datetime.now(timezone.utc).timestamp(),
        packet_id=str(uuid.uuid4()),
        lane="system",
        domain="core",
        channel="bootstrap",
        value={"demo": True},
        provenance={"source": "run_cycle_once"},
        rate=0.1,
        anomaly_flag=False,
        replay=False,
        phase=None,
    )


def run_cycle_once() -> None:
    """
    Execute one observational hydro cycle.

    Flow:
      observe → gate → enqueue → dispatch (trace only)
    """

    # ---------------- OBSERVE ----------------
    packet = observe_once()

    # ---------------- INGRES GATE ----------------
    decision = hydro_ingress_gate(packet)

    # ---------------- THROAT (enqueue) ----------------
    enqueue_if_admitted(packet, decision)

    # ---------------- STOP IF REJECTED ----------------
    if decision.gate_result == GateResult.REJECT:
        return

    # ---------------- DISPATCH (trace only) ----------------
    dispatch(packet, decision)


if __name__ == "__main__":
    run_cycle_once()

