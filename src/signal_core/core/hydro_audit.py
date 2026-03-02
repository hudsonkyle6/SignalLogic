# signal_core/core/hydro_audit.py

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Literal

from signal_core.core.hydro_types import HydroPacket
from rhythm_os.runtime.paths import AUDIT_PATH


def _hash_record(record: dict) -> str:
    blob = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def append_audit(
    packet: HydroPacket,
    decision: Literal["PASS", "QUARANTINE"],
    route: Literal["MAIN", "TURBINE"],
) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": datetime.now(timezone.utc).timestamp(),
        "packet_id": packet.packet_id,
        "t": packet.t,
        "lane": packet.lane,
        "domain": packet.domain,
        "channel": packet.channel,
        "route": route,
        "decision": decision,
        "value": packet.value,
        "phase": packet.phase,
        "provenance": packet.provenance,
    }

    record["hash"] = _hash_record(record)

    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
