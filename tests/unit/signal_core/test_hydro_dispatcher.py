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
- forest_proximity ≥ 0.70 → TURBINE (DLH — forest edge)
- forest_proximity 0.40–0.69 → MAIN + observe=True
- forest_proximity < 0.40 → MAIN + observe=False (normal)
- forest_proximity absent (None) → treated as 0.0 (normal routing)
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


# ------------------------------------------------------------------
# Lighthouse forest_proximity routing (v3)
# ------------------------------------------------------------------

class TestForestProximityRouting:
    def test_high_fp_forces_turbine_scout(self):
        # forest_proximity ≥ 0.70 → TURBINE (forest edge, no penstock commit)
        p = _packet(lane="system", forest_proximity=0.75)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "DLH_TURBINE_FOREST_EDGE"

    def test_exactly_at_scout_threshold_forces_turbine(self):
        p = _packet(lane="system", forest_proximity=0.70)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "DLH_TURBINE_FOREST_EDGE"

    def test_watch_zone_routes_main_with_observe(self):
        # 0.40 ≤ fp < 0.70 → MAIN + observe=True
        p = _packet(lane="system", forest_proximity=0.55)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is True

    def test_at_watch_lower_bound_routes_main_with_observe(self):
        p = _packet(lane="system", forest_proximity=0.40)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is True

    def test_just_below_watch_routes_main_no_observe(self):
        p = _packet(lane="system", forest_proximity=0.39)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is False

    def test_low_fp_routes_main_no_observe(self):
        # forest_proximity < 0.40 → normal routing, no observation
        p = _packet(lane="system", forest_proximity=0.10)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is False

    def test_no_annotation_treats_as_zero(self):
        # forest_proximity=None → default 0.0 → normal routing
        p = _packet(lane="system", forest_proximity=None)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is False

    def test_natural_watch_zone_routes_main_with_observe(self):
        p = _packet(lane="natural", domain="natural", forest_proximity=0.60)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.MAIN
        assert decision.observe is True
        assert decision.rule_id == "D1N_MAIN_ENVIRONMENTAL"

    def test_natural_high_fp_forces_turbine(self):
        p = _packet(lane="natural", domain="natural", forest_proximity=0.80)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.TURBINE
        assert decision.rule_id == "DLH_TURBINE_FOREST_EDGE"

    def test_spillway_rule_pre_empts_forest_routing(self):
        # D2 (pressure) must fire before DL-H forest check
        p = _packet(lane="system", anomaly_flag=True, forest_proximity=0.80)
        decision = dispatch(p, _ingress())
        assert decision.route == Route.SPILLWAY
        assert decision.rule_id == "D2_SPILLWAY_PRESSURE"

    def test_reject_pre_empts_forest_routing(self):
        # D0 must always fire first
        p = _packet(lane="system", forest_proximity=0.90)
        decision = dispatch(p, _ingress(GateResult.REJECT))
        assert decision.route == Route.DROP

    def test_observe_false_by_default_no_annotation(self):
        p = _packet()
        decision = dispatch(p, _ingress())
        assert decision.observe is False
