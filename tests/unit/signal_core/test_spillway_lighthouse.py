"""
Tests for signal_core.core.spillway_lighthouse

Invariants:
- forest_proximity ≥ 0.70 AND anomaly_flag → QUARANTINE
- forest_proximity ≥ 0.70 AND no anomaly → HOLD
- anomaly_flag alone (fp < 0.70) → HOLD
- no anomaly, low fp → RETURN (Turbine scout)
- result is always a SpillwayDecision with a non-empty reason
- assess_spillway is pure (no side effects)
"""

from __future__ import annotations

from signal_core.core.spillway_lighthouse import (
    assess_spillway,
    SpillwayDecision,
    SpillwayRoute,
)
from signal_core.core.hydro_types import HydroPacket

T_FIXED = 1705320000.0


def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id="pkt-spill-001",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.5},
        provenance={"source": "test"},
        anomaly_flag=False,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


# ------------------------------------------------------------------
# QUARANTINE — forest edge + anomaly
# ------------------------------------------------------------------


class TestQuarantine:
    def test_forest_edge_plus_anomaly_quarantines(self):
        p = _packet(forest_proximity=0.70, anomaly_flag=True)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.QUARANTINE

    def test_well_above_edge_plus_anomaly_quarantines(self):
        p = _packet(forest_proximity=0.95, anomaly_flag=True)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.QUARANTINE

    def test_quarantine_reason_non_empty(self):
        p = _packet(forest_proximity=0.80, anomaly_flag=True)
        result = assess_spillway(p)
        assert result.reason


# ------------------------------------------------------------------
# HOLD — forest edge without anomaly
# ------------------------------------------------------------------


class TestHoldForestEdge:
    def test_forest_edge_no_anomaly_holds(self):
        p = _packet(forest_proximity=0.70, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.HOLD

    def test_above_edge_no_anomaly_holds(self):
        p = _packet(forest_proximity=0.85, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.HOLD


# ------------------------------------------------------------------
# HOLD — anomaly flag without forest edge
# ------------------------------------------------------------------


class TestHoldAnomaly:
    def test_anomaly_below_forest_edge_holds(self):
        p = _packet(forest_proximity=0.30, anomaly_flag=True)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.HOLD

    def test_anomaly_mid_range_holds(self):
        p = _packet(forest_proximity=0.55, anomaly_flag=True)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.HOLD


# ------------------------------------------------------------------
# RETURN — low fp, no anomaly
# ------------------------------------------------------------------


class TestReturn:
    def test_low_fp_no_anomaly_returns(self):
        p = _packet(forest_proximity=0.20, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.RETURN

    def test_zero_fp_no_anomaly_returns(self):
        p = _packet(forest_proximity=0.0, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.RETURN

    def test_no_annotation_defaults_to_return(self):
        p = _packet()  # forest_proximity=None
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.RETURN

    def test_return_reason_non_empty(self):
        p = _packet(forest_proximity=0.10)
        result = assess_spillway(p)
        assert result.reason


# ------------------------------------------------------------------
# Threshold boundary conditions
# ------------------------------------------------------------------


class TestBoundary:
    def test_exactly_at_threshold_is_hold(self):
        p = _packet(forest_proximity=0.70, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.HOLD

    def test_just_below_threshold_with_no_anomaly_returns(self):
        p = _packet(forest_proximity=0.699, anomaly_flag=False)
        result = assess_spillway(p)
        assert result.route == SpillwayRoute.RETURN

    def test_returns_spillway_decision_type(self):
        p = _packet()
        result = assess_spillway(p)
        assert isinstance(result, SpillwayDecision)
