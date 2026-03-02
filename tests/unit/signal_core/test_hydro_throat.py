"""
Tests for signal_core.core.hydro_ingress_throat — enqueue_if_admitted

Invariants:
- REJECT decision → packet is silently dropped (no file written)
- PASS decision → packet is written to queue as valid JSON
- QUARANTINE decision → packet is written to queue (quarantined, not dropped)
- Written record includes temporal anchor phases (diurnal, semi_diurnal, long_wave)
- Written record contains the original packet fields
- Creates parent directories if they don't exist
- Multiple admitted packets accumulate as separate lines
"""

from __future__ import annotations

import json

import signal_core.core.hydro_ingress_throat as throat_mod
from signal_core.core.hydro_ingress_throat import enqueue_if_admitted
from signal_core.core.hydro_types import HydroPacket, IngressDecision, GateResult

T_FIXED = 1705320000.0


def _packet(packet_id: str = "pkt-throat-001", **overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id=packet_id,
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"v": 0.5},
        provenance={"source": "test"},
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _decision(result: GateResult, reason: str = "test") -> IngressDecision:
    return IngressDecision(gate_result=result, reason=reason)


# ------------------------------------------------------------------
# REJECT — drop silently
# ------------------------------------------------------------------


class TestRejectDrop:
    def test_reject_does_not_create_file(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet(), _decision(GateResult.REJECT))

        assert not queue_path.exists()

    def test_reject_returns_none(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        result = enqueue_if_admitted(_packet(), _decision(GateResult.REJECT))
        assert result is None


# ------------------------------------------------------------------
# PASS — enqueue
# ------------------------------------------------------------------


class TestPassEnqueue:
    def test_pass_creates_file(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet(), _decision(GateResult.PASS))

        assert queue_path.exists()

    def test_pass_writes_valid_json(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet("p-pass"), _decision(GateResult.PASS))

        lines = queue_path.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["packet_id"] == "p-pass"

    def test_pass_stamps_diurnal_phase(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet(), _decision(GateResult.PASS))

        record = json.loads(queue_path.read_text().strip())
        assert "diurnal_phase" in record
        assert record["diurnal_phase"] is not None
        assert 0.0 <= record["diurnal_phase"] <= 1.0

    def test_pass_stamps_all_anchor_phases(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet(), _decision(GateResult.PASS))

        record = json.loads(queue_path.read_text().strip())
        for phase_key in ["diurnal_phase", "semi_diurnal_phase", "long_wave_phase"]:
            assert phase_key in record
            assert isinstance(record[phase_key], float)


# ------------------------------------------------------------------
# QUARANTINE — enqueue (not drop)
# ------------------------------------------------------------------


class TestQuarantineEnqueue:
    def test_quarantine_writes_to_queue(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet("p-q"), _decision(GateResult.QUARANTINE))

        assert queue_path.exists()
        record = json.loads(queue_path.read_text().strip())
        assert record["packet_id"] == "p-q"

    def test_quarantine_stamps_phases(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet(), _decision(GateResult.QUARANTINE))

        record = json.loads(queue_path.read_text().strip())
        assert record["diurnal_phase"] is not None


# ------------------------------------------------------------------
# Multiple admissions
# ------------------------------------------------------------------


class TestMultipleAdmissions:
    def test_multiple_pass_packets_accumulate(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet("p1"), _decision(GateResult.PASS))
        enqueue_if_admitted(_packet("p2"), _decision(GateResult.PASS))
        enqueue_if_admitted(_packet("p3"), _decision(GateResult.QUARANTINE))

        lines = queue_path.read_text().strip().splitlines()
        assert len(lines) == 3
        ids = [json.loads(ln)["packet_id"] for ln in lines]
        assert ids == ["p1", "p2", "p3"]

    def test_reject_interspersed_does_not_add_line(self, tmp_path, monkeypatch):
        queue_path = tmp_path / "ingress.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", queue_path)

        enqueue_if_admitted(_packet("p1"), _decision(GateResult.PASS))
        enqueue_if_admitted(_packet("p-reject"), _decision(GateResult.REJECT))
        enqueue_if_admitted(_packet("p2"), _decision(GateResult.PASS))

        lines = queue_path.read_text().strip().splitlines()
        assert len(lines) == 2
        ids = [json.loads(ln)["packet_id"] for ln in lines]
        assert "p-reject" not in ids

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "queue.jsonl"
        monkeypatch.setattr(throat_mod, "QUEUE_PATH", nested)

        enqueue_if_admitted(_packet(), _decision(GateResult.PASS))

        assert nested.exists()
