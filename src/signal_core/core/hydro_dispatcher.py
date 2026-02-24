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

# v1: extremely conservative — only system may reach MAIN
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

    Rule priority (v1):

      D0: REJECT        → DROP
      D3: QUARANTINE   → TURBINE   (exploratory basin, no work extraction)
      D2: PRESSURE     → SPILLWAY  (relief path)
      D1: SAFE PASS    → MAIN      (boring, stable production)
      D4: FALLBACK     → TURBINE   (safety net)

    All returned decisions are descriptive,
    not executable authority.
    """

    pressure_class = classify_pressure(packet)

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
    # D2 — pressure relief (pre-empts MAIN)
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
    # D1 — boring, safe production path
    # ---------------------------------------------------------------
    if (
        ingress.gate_result == GateResult.PASS
        and pressure_class == "operational"
        and packet.lane in MAIN_LANES
    ):
        return DispatchDecision(
            Route.MAIN,
            "D1_MAIN_OPERATIONAL",
            pressure_class,
        )

    # ---------------------------------------------------------------
    # D4 — safety fallback (never committing)
    # ---------------------------------------------------------------
    return DispatchDecision(
        Route.TURBINE,
        "D4_SAFE_FALLBACK",
        pressure_class,
    )
