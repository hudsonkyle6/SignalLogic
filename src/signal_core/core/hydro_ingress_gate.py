"""
POSTURE: HYDRO
Sole authority to ADMIT signals.
Structural admission only.
No side effects.
No storage.
No routing.
No backflow permitted.

See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

import time
from typing import Iterable

from .hydro_types import HydroPacket, IngressDecision, GateResult


DEFAULT_ALLOWED_LANES = {
    "system",
    "market",
    "natural",
    "internal",
    "ops",
    "finance",
    "project",
    "narrative",
}


def _is_legible(value) -> bool:
    """
    Structural legibility only.
    Avoid huge blobs / binary-like junk.
    No interpretation of meaning.
    """
    try:
        s = str(value)
    except Exception:
        return False
    return len(s) <= 10_000


def hydro_ingress_gate(
    packet: HydroPacket,
    *,
    allowed_lanes: Iterable[str] = DEFAULT_ALLOWED_LANES,
    max_age_seconds: float = 24 * 3600,
    now: float | None = None,
) -> IngressDecision:
    """
    Structural admission only.

    Checks:
      - schema: critical fields exist and are typed
      - lane admissibility
      - provenance presence (minimal identity)
      - freshness (unless replay)
      - legibility

    Returns:
      IngressDecision(PASS | QUARANTINE | REJECT, reason)

    NO interpretation.
    NO optimization.
    NO side effects.
    """

    now = time.time() if now is None else float(now)

    # ---------------- Schema ----------------
    if not packet.packet_id or not isinstance(packet.packet_id, str):
        return IngressDecision(GateResult.REJECT, "G0_SCHEMA_packet_id")

    if not packet.lane or not isinstance(packet.lane, str):
        return IngressDecision(GateResult.REJECT, "G0_SCHEMA_lane")

    if not packet.domain or not isinstance(packet.domain, str):
        return IngressDecision(GateResult.REJECT, "G0_SCHEMA_domain")

    if not isinstance(packet.provenance, dict):
        return IngressDecision(GateResult.REJECT, "G0_SCHEMA_provenance")

    # ---------------- Lane ----------------
    if packet.lane not in set(allowed_lanes):
        return IngressDecision(GateResult.REJECT, "G1_LANE_not_admissible")

    # ---------------- Provenance ----------------
    # Minimal identity only — truth is not evaluated
    if "source" not in packet.provenance:
        return IngressDecision(
            GateResult.QUARANTINE,
            "G2_PROVENANCE_missing_source",
        )

    # ---------------- Freshness ----------------
    if not packet.replay:
        age = now - float(packet.t)

        if age < -300:
            return IngressDecision(
                GateResult.QUARANTINE,
                "G3_FRESHNESS_future_timestamp",
            )

        if age > float(max_age_seconds):
            return IngressDecision(
                GateResult.QUARANTINE,
                "G3_FRESHNESS_stale",
            )

    # ---------------- Legibility ----------------
    if not _is_legible(packet.value):
        return IngressDecision(
            GateResult.QUARANTINE,
            "G4_LEGIBILITY_unreadable",
        )

    # ---------------- Pass ----------------
    return IngressDecision(GateResult.PASS, "G5_PASS")
