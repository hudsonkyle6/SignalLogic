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
import time

from .hydro_types import HydroPacket, IngressDecision, GateResult
from rhythm_os.runtime.temporal_anchor import compute_anchor
from rhythm_os.runtime.paths import QUEUE_PATH


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

    # Stamp temporal anchor phases onto the packet before persisting.
    # The anchor is derived from the packet's own timestamp so the phase
    # reflects when the signal was observed, not when it was admitted.
    t_ref = float(packet.t) if packet.t else time.time()
    anchor = compute_anchor(t_ref, domain=packet.domain)

    stamped = HydroPacket(
        **{
            **packet.__dict__,
            "diurnal_phase": anchor.diurnal_phase,
            "semi_diurnal_phase": anchor.semi_diurnal_phase,
            "long_wave_phase": anchor.long_wave_phase,
        }
    )

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                stamped.__dict__,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
