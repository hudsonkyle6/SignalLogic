"""
POSTURE: HYDRO INGRESS QUEUE
Append-only queue reader/drainer.

- Writer: hydro_ingress_throat.enqueue_if_admitted()
- Reader: drain_queue() here
- No interpretation. No routing. No authority beyond moving packets.
"""

from __future__ import annotations

import json
from typing import List

from .hydro_types import HydroPacket
from rhythm_os.runtime.paths import QUEUE_PATH


def drain_queue(*, max_items: int | None = None) -> List[HydroPacket]:
    """
    Drain (consume) queued packets.

    Semantics:
    - If file missing or empty → []
    - Reads lines in order
    - Truncates file after read (atomic enough for single-writer use)
    - If max_items set, drains only that many and preserves the rest

    Assumption (Canon v1):
    - Single writer (run_cycle_once)
    - Single drainer (hydro_run_cadence)
    """
    if not QUEUE_PATH.exists():
        return []

    text = QUEUE_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []

    lines = text.splitlines()

    if max_items is None or max_items >= len(lines):
        drained = lines
        remaining = []
    else:
        drained = lines[:max_items]
        remaining = lines[max_items:]

    # Write back remaining (truncate)
    if remaining:
        QUEUE_PATH.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        QUEUE_PATH.write_text("", encoding="utf-8")

    packets: List[HydroPacket] = []
    for line in drained:
        data = json.loads(line)
        packets.append(HydroPacket(**data))

    return packets
