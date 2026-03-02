"""
POSTURE: PENSTOCK OUTPUT

Real-time control signal channel.

Emits a structured record for every MAIN-committed packet so downstream
systems — grid controllers, vessel management, alerting pipelines, SIEMs —
can act on dispatch decisions without polling the dark field.

Authority:
  - Append-only write to CONTROL_DIR/signals-YYYY-MM-DD.jsonl (daily rotation)
  - NO authority over routing
  - NO modification of packets or decisions
  - NO reads from penstock or queue

Consumers tail the current day's file.  Each line is a self-contained JSON
record describing one control action.  A new file starts at UTC midnight;
no rotation of old files is needed — they accumulate as the audit trail.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from signal_core.core.hydro_types import HydroPacket, DispatchDecision
from rhythm_os.runtime.paths import CONTROL_DIR


def emit_control_signal(packet: HydroPacket, decision: DispatchDecision) -> None:
    """
    Append a control signal record to today's rolling signals log.

    Called after every successful MAIN commit.  The record contains the
    full routing context so downstream consumers can act without re-reading
    the dark field.

    Files rotate at UTC midnight: signals-YYYY-MM-DD.jsonl.
    """
    record = {
        "ts": time.time(),
        "packet_id": packet.packet_id,
        "t": packet.t,
        "domain": packet.domain,
        "lane": packet.lane,
        "channel": packet.channel,
        "route": decision.route.value,
        "rule_id": decision.rule_id,
        "pressure_class": decision.pressure_class,
        "observe": decision.observe,
        "forest_proximity": packet.forest_proximity,
        "seasonal_band": packet.seasonal_band,
        "coherence": (packet.value or {}).get("coherence"),
        "diurnal_phase": packet.diurnal_phase,
    }

    today = datetime.now(timezone.utc).date().isoformat()
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTROL_DIR / f"signals-{today}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
