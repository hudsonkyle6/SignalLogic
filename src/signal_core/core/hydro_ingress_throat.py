"""
POSTURE: HYDRO THROAT
Append-only ingress queue.

This module performs the FIRST irreversible act
after admission: persistence.

No interpretation.
No routing.
No authority beyond append.
"""

from __future__ import annotations

import json
from pathlib import Path

from .hydro_types import HydroPacket, IngressDecision, GateResult


# Canonical ingress queue (append-only)
QUEUE_PATH = Path("src/rhythm_os/data/dark_field/hydro/ingress.jsonl")


def enqueue_if_admitted(
    packet: HydroPacket,
    decision: IngressDecision,
) -> None:
    """
    Append packet to ingress queue if admitted.

    Rules:
      - PASS       → enqueue
      - QUARANTINE → enqueue
      - REJECT     → drop silently
    """
    if decision.gate_result == GateResult.REJECT:
        return

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                packet.__dict__,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
