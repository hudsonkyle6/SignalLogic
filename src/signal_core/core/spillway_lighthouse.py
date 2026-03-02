"""
POSTURE: TRIBUTARY (Auxiliary Spillway Lighthouse)

Second look at SPILLWAY-routed packets. Sits between the spillway basin
and the re-routing decision. Read-only. No authority over penstock.

The main Lighthouse annotates packets before the gate; this module evaluates
packets that have already been routed to the SPILLWAY and decides how to
handle them:

  RETURN      → Send to Turbine for phase observation (re-entry path)
  HOLD        → Accumulate in spillway; investigate on next cycle
  QUARANTINE  → Isolate completely; no re-entry, raise alert

Decision rules (Phase A — rule-based, no ML):

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ forest_proximity ≥ 0.70  AND anomaly_flag  → QUARANTINE                │
  │ forest_proximity ≥ 0.70                    → HOLD (forest edge, watch) │
  │ anomaly_flag                               → HOLD (structural anomaly)  │
  │ otherwise                                  → RETURN (Turbine scout)    │
  └─────────────────────────────────────────────────────────────────────────┘

NO learning. NO persistence. NO side effects beyond returning a decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .hydro_types import HydroPacket


# ---------------------------------------------------------------------------
# Spillway routing outcomes
# ---------------------------------------------------------------------------


class SpillwayRoute(str, Enum):
    RETURN = "RETURN"  # → Turbine re-entry for phase observation
    HOLD = "HOLD"  # → Stay in spillway; review next cycle
    QUARANTINE = "QUARANTINE"  # → Isolated; no re-entry; alert


@dataclass(frozen=True)
class SpillwayDecision:
    route: SpillwayRoute
    reason: str


# ---------------------------------------------------------------------------
# Thresholds (mirror dispatcher constants for consistency)
# ---------------------------------------------------------------------------

_FOREST_EDGE = 0.70  # forest_proximity at or above this = near edge


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def assess_spillway(packet: HydroPacket) -> SpillwayDecision:
    """
    Non-authoritative second look at a spillway-routed packet.

    Returns a SpillwayDecision indicating how to handle the packet next.
    This module has NO write authority — callers act on the decision.

    POSTURE: TRIBUTARY — read-only, no side effects.
    """
    fp = float(packet.forest_proximity) if packet.forest_proximity is not None else 0.0
    anomaly = bool(packet.anomaly_flag)

    # Near forest edge + anomaly → hard quarantine
    if fp >= _FOREST_EDGE and anomaly:
        return SpillwayDecision(
            route=SpillwayRoute.QUARANTINE,
            reason=f"SL_QUARANTINE_forest_edge_anomaly fp={fp:.3f}",
        )

    # Near forest edge (no anomaly) → hold and watch
    if fp >= _FOREST_EDGE:
        return SpillwayDecision(
            route=SpillwayRoute.HOLD,
            reason=f"SL_HOLD_forest_edge fp={fp:.3f}",
        )

    # Structural anomaly but not at forest edge → hold
    if anomaly:
        return SpillwayDecision(
            route=SpillwayRoute.HOLD,
            reason="SL_HOLD_anomaly_flag",
        )

    # Default: return to Turbine for observation
    return SpillwayDecision(
        route=SpillwayRoute.RETURN,
        reason="SL_RETURN_turbine_scout",
    )
