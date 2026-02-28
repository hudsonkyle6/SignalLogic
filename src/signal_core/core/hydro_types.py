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

    # ─────────────────────────────
    # Temporal anchor (stamped at ingress throat)
    # ─────────────────────────────
    diurnal_phase: Optional[float] = None       # position in 24h cycle [0, 1]
    semi_diurnal_phase: Optional[float] = None  # position in 12h cycle [0, 1]
    long_wave_phase: Optional[float] = None     # position in ~28d cycle [0, 1]

    # ─────────────────────────────
    # Lighthouse annotation (stamped before gate — NO AUTHORITY)
    # Read-only seasonal context. Gate ignores these entirely.
    # Dispatcher may use forest_proximity for routing orientation.
    # ─────────────────────────────
    seasonal_band: Optional[str] = None         # "winter" | "spring_transition" | "summer" | "fall_transition"
    pattern_confidence: Optional[float] = None  # [0, 1] — stability of current seasonal pattern
    forest_proximity: Optional[float] = None    # [0, 1] — 0 = pasture center, 1 = forest edge
    afterglow_decay: Optional[float] = None     # [0.2, 0.9] — wave memory decay rate


@dataclass(frozen=True)
class IngressDecision:
    gate_result: GateResult
    reason: str


@dataclass(frozen=True)
class DispatchDecision:
    route: Route
    rule_id: str
    pressure_class: str
    observe: bool = False   # True → also send to Turbine for concurrent observation
