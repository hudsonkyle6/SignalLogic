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

from signal_core.core.hydro_types import HydroPacket, GateResult
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_ingress_throat import enqueue_if_admitted
from signal_core.core.hydro_dispatcher import dispatch
from signal_core.core.instruments.system_observe import sample_once


def observe_once() -> HydroPacket:
    """
    Produce a single system-metrics observational packet.

    Reads live CPU, memory, network, and frequency via psutil.
    Falls back to a minimal bootstrap packet if psutil is unavailable.
    """
    return sample_once()


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
