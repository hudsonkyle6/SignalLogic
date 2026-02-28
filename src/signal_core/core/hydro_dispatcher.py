"""
POSTURE: HYDRO (DISPATCH ONLY)

Sole authority to ROUTE pressure.
NO authority to COMMIT penstock.
NO authority to WRITE.

Witnessing and persistence occur ONLY
after successful dispatch + commit.

See: rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

from .hydro_types import (
    HydroPacket,
    IngressDecision,
    DispatchDecision,
    GateResult,
    Route,
)

# ---------------------------------------------------------------------
# Static classification (NO learning, NO mutation)
# ---------------------------------------------------------------------

LANE_TO_PRESSURE_CLASS = {
    "system": "operational",
    "ops": "operational",
    "internal": "operational",

    "market": "volatility",
    "finance": "volatility",

    "natural": "environmental",
    "project": "workload",
    "narrative": "turbidity",
}

# v1: system operational lane
# v2: natural environmental lane added (live Open-Meteo field data)
MAIN_LANES = {"system"}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def classify_pressure(packet: HydroPacket) -> str:
    """
    Deterministic, static classification.
    No inference. No memory.
    """
    return LANE_TO_PRESSURE_CLASS.get(packet.lane, "unknown")


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------

# Forest proximity thresholds (Lighthouse annotation — no authority over gate)
FOREST_SCOUT_THRESHOLD = 0.70   # ≥ this → Turbine scout only (no penstock commit)
FOREST_WATCH_THRESHOLD = 0.40   # ≥ this → commit to MAIN but also observe in Turbine


def _forest_proximity(packet: HydroPacket) -> float:
    """
    Read the Lighthouse forest_proximity annotation from the packet.
    Returns 0.0 if no annotation (treat as deep-pasture / fully normal).
    """
    fp = packet.forest_proximity
    if fp is None:
        return 0.0
    return float(fp)


def dispatch(
    packet: HydroPacket,
    ingress: IngressDecision,
    *,
    rate_threshold: float = 1.0,
) -> DispatchDecision:
    """
    Deterministic routing.

    ROUTING ONLY — NO COMMIT AUTHORITY
    ROUTING ONLY — NO PERSISTENCE

    Rule priority (v3 — adds Lighthouse forest_proximity orientation):

      D0:   REJECT                         → DROP
      D3:   QUARANTINE / replay            → TURBINE   (exploratory basin)
      D2:   PRESSURE (rate/anomaly)        → SPILLWAY  (relief path)
      DL-H: forest_proximity ≥ 0.70        → TURBINE   (scout only — forest edge)
      D1:   OPERATIONAL                    → MAIN      (system lane)
            forest_proximity 0.40–0.69    → MAIN + observe=True (dual observation)
      D1-N: ENVIRONMENTAL                  → MAIN      (natural lane)
            forest_proximity 0.40–0.69    → MAIN + observe=True
      D4:   FALLBACK                       → TURBINE   (safety net)

    forest_proximity is read from the Lighthouse annotation on the packet.
    If absent (None), it defaults to 0.0 (deep-pasture, no restriction).
    The gate is never consulted about Lighthouse fields — they are invisible to it.

    All returned decisions are descriptive, not executable authority.
    """

    pressure_class = classify_pressure(packet)
    fp = _forest_proximity(packet)

    # ---------------------------------------------------------------
    # D0 — hard structural rejection
    # ---------------------------------------------------------------
    if ingress.gate_result == GateResult.REJECT:
        return DispatchDecision(
            Route.DROP,
            "D0_REJECT",
            pressure_class,
        )

    # ---------------------------------------------------------------
    # D3 — exploratory basin (quarantine or replay)
    # ---------------------------------------------------------------
    if ingress.gate_result == GateResult.QUARANTINE or bool(packet.replay):
        return DispatchDecision(
            Route.TURBINE,
            "D3_TURBINE_EXPLORATORY",
            pressure_class,
        )

    # ---------------------------------------------------------------
    # D2 — pressure relief (pre-empts MAIN and forest routing)
    # ---------------------------------------------------------------
    if ingress.gate_result == GateResult.PASS and pressure_class == "operational":
        if (
            packet.rate is not None
            and float(packet.rate) > float(rate_threshold)
        ) or bool(packet.anomaly_flag):
            return DispatchDecision(
                Route.SPILLWAY,
                "D2_SPILLWAY_PRESSURE",
                pressure_class,
            )

    # ---------------------------------------------------------------
    # DL-H — Lighthouse forest edge: scout only, no penstock commit
    # Applied to MAIN-eligible packets that are near the forest edge.
    # ---------------------------------------------------------------
    if fp >= FOREST_SCOUT_THRESHOLD:
        return DispatchDecision(
            Route.TURBINE,
            "DLH_TURBINE_FOREST_EDGE",
            pressure_class,
        )

    # ---------------------------------------------------------------
    # D1 — boring, safe production path
    # Packets in the watch zone (0.40 ≤ fp < 0.70) commit to MAIN
    # but are simultaneously flagged for Turbine observation.
    # ---------------------------------------------------------------
    if (
        ingress.gate_result == GateResult.PASS
        and pressure_class == "operational"
        and packet.lane in MAIN_LANES
    ):
        observe = fp >= FOREST_WATCH_THRESHOLD
        return DispatchDecision(
            Route.MAIN,
            "D1_MAIN_OPERATIONAL",
            pressure_class,
            observe=observe,
        )

    # ---------------------------------------------------------------
    # D1-N — natural environmental signals (live field data → penstock)
    # ---------------------------------------------------------------
    if (
        ingress.gate_result == GateResult.PASS
        and pressure_class == "environmental"
        and packet.lane == "natural"
    ):
        observe = fp >= FOREST_WATCH_THRESHOLD
        return DispatchDecision(
            Route.MAIN,
            "D1N_MAIN_ENVIRONMENTAL",
            pressure_class,
            observe=observe,
        )

    # ---------------------------------------------------------------
    # D4 — safety fallback (never committing)
    # ---------------------------------------------------------------
    return DispatchDecision(
        Route.TURBINE,
        "D4_SAFE_FALLBACK",
        pressure_class,
    )
