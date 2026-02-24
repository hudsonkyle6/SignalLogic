#C:\Users\SignalADmin\Signal Archive\SignalLogic\src\signal_core\core\lighthouse.py
"""
POSTURE: TRIBUTARY
Hypothesis-only. Must not write to Penstock.
See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from .hydro_types import HydroPacket, DispatchDecision


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
