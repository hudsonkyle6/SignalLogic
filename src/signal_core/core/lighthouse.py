"""
POSTURE: TRIBUTARY
Hypothesis-only. Must not write to Penstock.
See rhythm_os/TWO_WATERS.md

Two responsibilities:

1. annotate_packet() — PRE-GATE seasonal annotation.
   Reads seasonal_prior for the packet's timestamp and stamps the packet
   with seasonal_band, pattern_confidence, forest_proximity, and afterglow_decay.
   The gate ignores these fields entirely (purely structural).
   The dispatcher uses forest_proximity to orient routing.

2. illuminate() — POST-DISPATCH structural labeling.
   Non-authoritative summary of what was observed and where it was routed.
   No truth claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from .hydro_types import HydroPacket, DispatchDecision
from rhythm_os.runtime.seasonal_prior import compute_seasonal_prior


# ---------------------------------------------------------------------------
# Pre-gate annotation
# ---------------------------------------------------------------------------

def annotate_packet(packet: HydroPacket) -> HydroPacket:
    """
    Stamp seasonal Lighthouse annotations onto the packet BEFORE the gate.

    Returns a NEW (frozen) HydroPacket with seasonal context fields filled.
    If annotation fails for any reason, returns the original packet unchanged
    (fail-open — the gate must still decide structurally).

    POSTURE: TRIBUTARY — no authority, no persistence, no side effects.
    """
    if packet.seasonal_band is not None:
        # Already annotated (e.g. re-processed replay packet)
        return packet

    try:
        prior = compute_seasonal_prior(float(packet.t))
    except Exception:
        return packet  # fail-open: seasonal context is informational only

    return HydroPacket(
        **{
            **packet.__dict__,
            "seasonal_band": prior.seasonal_band,
            "pattern_confidence": prior.pattern_confidence,
            "forest_proximity": prior.forest_proximity,
            "afterglow_decay": prior.afterglow_decay,
        }
    )


# ---------------------------------------------------------------------------
# Post-dispatch illumination
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LighthouseSummary:
    packet_id: str
    route: str
    pressure_class: str
    note: str
    hypothesis: bool
    features: Dict[str, Any]


def illuminate(packet: HydroPacket, decision: DispatchDecision) -> LighthouseSummary:
    """
    Non-authoritative illumination only.
    No truth claims.
    """
    features: Dict[str, Any] = {
        "lane": packet.lane,
        "domain": packet.domain,
        "channel": packet.channel,
        "rate": packet.rate,
        "anomaly_flag": packet.anomaly_flag,
        "replay": packet.replay,
    }

    # No interpretation of meaning; only structural/contextual labeling.
    note = "observation"
    hypothesis = False

    if decision.route.value == "TURBINE":
        note = "exploratory basin (non-production)"
        hypothesis = True

    if decision.route.value == "SPILLWAY":
        note = "pressure relief path (operational)"
        hypothesis = True

    return LighthouseSummary(
        packet_id=packet.packet_id,
        route=decision.route.value,
        pressure_class=decision.pressure_class,
        note=note,
        hypothesis=hypothesis,
        features=features,
    )
