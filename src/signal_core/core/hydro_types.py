from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class GateResult(str, Enum):
    PASS = "PASS"
    QUARANTINE = "QUARANTINE"
    REJECT = "REJECT"


class Route(str, Enum):
    MAIN = "MAIN"
    SPILLWAY = "SPILLWAY"
    TURBINE = "TURBINE"
    DROP = "DROP"


@dataclass(frozen=True)
class HydroPacket:
    """
    Transport envelope from ingress to Hydro.

    NO authority.
    NO mutation.
    NO decision logic.
    """

    # Core identity
    t: float
    packet_id: str
    lane: str
    domain: str
    channel: str

    # Raw observational payload
    value: Dict[str, Any]
    provenance: Dict[str, Any]

    # Optional flow metadata
    rate: float | None = None
    anomaly_flag: bool = False
    replay: bool = False

    # ─────────────────────────────
    # Rhythm coupling (NO AUTHORITY)
    # ─────────────────────────────
    phase: Optional[float] = None

    # True phase coherence (0–1)
    coherence: Optional[float] = None


@dataclass(frozen=True)
class IngressDecision:
    gate_result: GateResult
    reason: str


@dataclass(frozen=True)
class DispatchDecision:
    route: Route
    rule_id: str
    pressure_class: str
