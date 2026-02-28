"""
Tests for signal_core.core.hydro_ingress_gate

Invariants:
- Valid packets → PASS
- Missing required fields → REJECT
- Unknown lane → REJECT
- Missing provenance source → QUARANTINE
- Future timestamp (>5 min) → QUARANTINE
- Stale timestamp → QUARANTINE
- Unreadable value → QUARANTINE
- Replay flag bypasses freshness checks
"""
from __future__ import annotations

import time
import pytest

from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_types import HydroPacket, GateResult


def _packet(**overrides) -> HydroPacket:
    """Build a minimal valid HydroPacket, with optional field overrides."""
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


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------

class TestPass:
    def test_valid_system_packet_passes(self):
        result = hydro_ingress_gate(_packet())
        assert result.gate_result == GateResult.PASS

    def test_valid_natural_packet_passes(self):
        result = hydro_ingress_gate(_packet(lane="natural", domain="natural"))
        assert result.gate_result == GateResult.PASS

    def test_valid_market_packet_passes(self):
        result = hydro_ingress_gate(_packet(lane="market", domain="market"))
        assert result.gate_result == GateResult.PASS


# ------------------------------------------------------------------
# Schema rejections
# ------------------------------------------------------------------

class TestSchemaReject:
    def test_empty_packet_id_rejected(self):
        result = hydro_ingress_gate(_packet(packet_id=""))
        assert result.gate_result == GateResult.REJECT
        assert "packet_id" in result.reason

    def test_empty_lane_rejected(self):
        result = hydro_ingress_gate(_packet(lane=""))
        assert result.gate_result == GateResult.REJECT
        assert "lane" in result.reason

    def test_empty_domain_rejected(self):
        result = hydro_ingress_gate(_packet(domain=""))
        assert result.gate_result == GateResult.REJECT
        assert "domain" in result.reason

    def test_non_dict_provenance_rejected(self):
        result = hydro_ingress_gate(_packet(provenance="not-a-dict"))
        assert result.gate_result == GateResult.REJECT
        assert "provenance" in result.reason


# ------------------------------------------------------------------
# Lane rejections
# ------------------------------------------------------------------

class TestLaneReject:
    def test_unknown_lane_rejected(self):
        result = hydro_ingress_gate(_packet(lane="garbage"))
        assert result.gate_result == GateResult.REJECT
        assert "LANE" in result.reason


# ------------------------------------------------------------------
# Quarantine cases
# ------------------------------------------------------------------

class TestQuarantine:
    def test_missing_provenance_source_quarantined(self):
        result = hydro_ingress_gate(_packet(provenance={}))
        assert result.gate_result == GateResult.QUARANTINE
        assert "PROVENANCE" in result.reason

    def test_future_timestamp_quarantined(self):
        future = time.time() + 600  # 10 minutes in future
        result = hydro_ingress_gate(_packet(t=future))
        assert result.gate_result == GateResult.QUARANTINE
        assert "FRESHNESS" in result.reason

    def test_stale_timestamp_quarantined(self):
        old = time.time() - (25 * 3600)  # 25 hours ago
        result = hydro_ingress_gate(_packet(t=old))
        assert result.gate_result == GateResult.QUARANTINE
        assert "FRESHNESS" in result.reason

    def test_oversized_value_quarantined(self):
        huge_value = "x" * 11_000
        result = hydro_ingress_gate(_packet(value=huge_value))
        assert result.gate_result == GateResult.QUARANTINE
        assert "LEGIBILITY" in result.reason


# ------------------------------------------------------------------
# Replay flag
# ------------------------------------------------------------------

class TestReplay:
    def test_replay_bypasses_freshness(self):
        old = time.time() - (25 * 3600)
        result = hydro_ingress_gate(_packet(t=old, replay=True))
        assert result.gate_result == GateResult.PASS


# ------------------------------------------------------------------
# Legibility exception branch (_is_legible: str() raises)
# ------------------------------------------------------------------

class TestLegibilityException:
    def test_unrepresentable_value_quarantined(self):
        class BadStr:
            def __str__(self):
                raise RuntimeError("cannot stringify")

        result = hydro_ingress_gate(_packet(value=BadStr()))
        assert result.gate_result == GateResult.QUARANTINE
        assert "LEGIBILITY" in result.reason
