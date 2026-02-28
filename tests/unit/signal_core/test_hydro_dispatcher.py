"""
Tests for signal_core.core.hydro_dispatcher

Invariants:
- REJECT → DROP (D0)
- QUARANTINE → TURBINE (D3)
- replay=True → TURBINE (D3)
- system PASS, no pressure → MAIN (D1)
- system PASS, rate > threshold → SPILLWAY (D2)
- system PASS, anomaly_flag → SPILLWAY (D2)
- natural PASS → MAIN (D1-N)
- unknown/cyber PASS → TURBINE (D4)
- routing is deterministic (same input → same output)
"""
from __future__ import annotations

import time
import pytest

from signal_core.core.hydro_dispatcher import dispatch
from signal_core.core.hydro_types import (
    HydroPacket,
    IngressDecision,
    GateResult,
    Route,
)


def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=time.time(),
        packet_id="test-001",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.75},
        provenance={"source": "test"},
        rate=None,
        anomaly_flag=False,
        replay=False,
        phase=0.0,
        coherence=0.75,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _ingress(result: GateResult = GateResult.PASS, reason: str = "G5_PASS") -> IngressDecision:
    return IngressDecision(gate_result=result, reason=reason)


# ------------------------------------------------------------------
# D0 — REJECT → DROP
# ------------------------------------------------------------------

class TestD0Reject:
    def test_rejected_packet_drops(self):
        decision = dispatch(_packet(), _ingress(GateResult.REJECT))
        assert decision.route == Route.DROP
        assert decision.rule_id == "D0_REJECT"


# ------------------------------------------------------------------
# D3 — QUARANTINE / replay → TURBINE
# ------------------------------------------------------------------

class TestD3Turbine:
    def test_quarantined_packet_goes_to_turbine(self):
        decision = dispatch(_packet(), _ingress(GateResult.QUARANTINE))
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "D3_TURBINE_EXPLORATORY"

    def test_replay_packet_goes_to_turbine(self):
        decision = dispatch(_packet(replay=True), _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "D3_TURBINE_EXPLORATORY"


# ------------------------------------------------------------------
# D2 — pressure relief → SPILLWAY
# ------------------------------------------------------------------

class TestD2Spillway:
    def test_high_rate_goes_to_spillway(self):
        decision = dispatch(_packet(rate=2.5), _ingress(), rate_threshold=1.0)
        assert decision.route == Route.SPILLWAY
        assert decision.rule_id == "D2_SPILLWAY_PRESSURE"

    def test_anomaly_flag_goes_to_spillway(self):
        decision = dispatch(_packet(anomaly_flag=True), _ingress())
        assert decision.route == Route.SPILLWAY
        assert decision.rule_id == "D2_SPILLWAY_PRESSURE"

    def test_rate_at_threshold_not_spillway(self):
        # Exactly at threshold is not over it
        decision = dispatch(_packet(rate=1.0), _ingress(), rate_threshold=1.0)
        assert decision.route == Route.MAIN


# ------------------------------------------------------------------
# D1 — operational → MAIN
# ------------------------------------------------------------------

class TestD1Main:
    def test_system_pass_goes_to_main(self):
        decision = dispatch(_packet(lane="system"), _ingress())
        assert decision.route == Route.MAIN
        assert decision.rule_id == "D1_MAIN_OPERATIONAL"

    def test_ops_falls_to_turbine_not_in_main_lanes(self):
        # ops is operational pressure class but not yet in MAIN_LANES — falls to D4
        decision = dispatch(_packet(lane="ops", domain="ops"), _ingress())
        assert decision.route == Route.TURBINE

    def test_internal_falls_to_turbine_not_in_main_lanes(self):
        # internal is operational pressure class but not yet in MAIN_LANES — falls to D4
        decision = dispatch(_packet(lane="internal", domain="internal"), _ingress())
        assert decision.route == Route.TURBINE


# ------------------------------------------------------------------
# D1-N — natural environmental → MAIN
# ------------------------------------------------------------------

class TestD1NEnvironmental:
    def test_natural_pass_goes_to_main(self):
        decision = dispatch(_packet(lane="natural", domain="natural"), _ingress())
        assert decision.route == Route.MAIN
        assert decision.rule_id == "D1N_MAIN_ENVIRONMENTAL"


# ------------------------------------------------------------------
# D4 — fallback → TURBINE
# ------------------------------------------------------------------

class TestD4Fallback:
    def test_cyber_pass_falls_to_turbine(self):
        decision = dispatch(_packet(lane="cyber", domain="cyber"), _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "D4_SAFE_FALLBACK"

    def test_market_pass_falls_to_turbine(self):
        decision = dispatch(_packet(lane="market", domain="market"), _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "D4_SAFE_FALLBACK"

    def test_narrative_falls_to_turbine(self):
        decision = dispatch(_packet(lane="narrative", domain="narrative"), _ingress())
        assert decision.route == Route.TURBINE


# ------------------------------------------------------------------
# Determinism
# ------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_route(self):
        p = _packet(lane="system", rate=None)
        ing = _ingress()
        d1 = dispatch(p, ing)
        d2 = dispatch(p, ing)
        assert d1.route == d2.route
        assert d1.rule_id == d2.rule_id

    def test_dispatch_does_not_mutate_packet(self):
        p = _packet()
        original_lane = p.lane
        dispatch(p, _ingress())
        assert p.lane == original_lane
