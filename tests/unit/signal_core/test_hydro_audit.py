"""
Tests for signal_core.core.hydro_audit

Invariants:
- _hash_record is deterministic: same input → same SHA-256 hex
- _hash_record is sensitive to content: different input → different hash
- append_audit writes a valid JSON line with all expected fields
- append_audit includes a non-empty hash field
- append_audit creates parent directories if absent
- Multiple appends accumulate as separate lines
"""

from __future__ import annotations

import json

import signal_core.core.hydro_audit as audit_mod
from signal_core.core.hydro_audit import _hash_record, append_audit
from signal_core.core.hydro_types import HydroPacket


def _packet(packet_id: str = "pkt-audit-001", domain: str = "system") -> HydroPacket:
    return HydroPacket(
        t=1705320000.0,
        packet_id=packet_id,
        lane="system",
        domain=domain,
        channel="net_pressure",
        value={"v": 0.75},
        provenance={"source": "unit_test"},
        phase=0.3,
        coherence=0.9,
    )


# ------------------------------------------------------------------
# _hash_record
# ------------------------------------------------------------------


class TestHashRecord:
    def test_deterministic(self):
        record = {"a": 1, "b": "hello"}
        assert _hash_record(record) == _hash_record(record)

    def test_same_content_same_hash(self):
        r1 = {"x": 42, "y": "world"}
        r2 = {"x": 42, "y": "world"}
        assert _hash_record(r1) == _hash_record(r2)

    def test_different_content_different_hash(self):
        r1 = {"x": 1}
        r2 = {"x": 2}
        assert _hash_record(r1) != _hash_record(r2)

    def test_returns_hex_string(self):
        h = _hash_record({"key": "value"})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest length
        int(h, 16)  # must be valid hexadecimal

    def test_key_order_does_not_matter(self):
        r1 = {"a": 1, "b": 2}
        r2 = {"b": 2, "a": 1}
        assert _hash_record(r1) == _hash_record(r2)


# ------------------------------------------------------------------
# append_audit
# ------------------------------------------------------------------


class TestAppendAudit:
    def test_creates_file_with_valid_json(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", audit_path)

        append_audit(_packet(), decision="PASS", route="MAIN")

        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["packet_id"] == "pkt-audit-001"

    def test_record_contains_all_fields(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", audit_path)

        append_audit(_packet(), decision="QUARANTINE", route="TURBINE")

        record = json.loads(audit_path.read_text().strip())
        for field in [
            "ts",
            "packet_id",
            "t",
            "lane",
            "domain",
            "channel",
            "route",
            "decision",
            "value",
            "phase",
            "provenance",
            "hash",
        ]:
            assert field in record, f"Missing field: {field}"

    def test_record_decision_and_route_match(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", audit_path)

        append_audit(_packet(), decision="PASS", route="MAIN")

        record = json.loads(audit_path.read_text().strip())
        assert record["decision"] == "PASS"
        assert record["route"] == "MAIN"

    def test_hash_is_non_empty_hex(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", audit_path)

        append_audit(_packet(), decision="PASS", route="MAIN")

        record = json.loads(audit_path.read_text().strip())
        h = record["hash"]
        assert isinstance(h, str) and len(h) == 64
        int(h, 16)  # valid hex

    def test_multiple_appends_produce_separate_lines(self, tmp_path, monkeypatch):
        audit_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", audit_path)

        append_audit(_packet("p1"), decision="PASS", route="MAIN")
        append_audit(_packet("p2"), decision="QUARANTINE", route="TURBINE")

        lines = audit_path.read_text().strip().splitlines()
        assert len(lines) == 2
        ids = [json.loads(ln)["packet_id"] for ln in lines]
        assert ids == ["p1", "p2"]

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        nested_path = tmp_path / "deep" / "nested" / "audit.jsonl"
        monkeypatch.setattr(audit_mod, "AUDIT_PATH", nested_path)

        append_audit(_packet(), decision="PASS", route="MAIN")

        assert nested_path.exists()
