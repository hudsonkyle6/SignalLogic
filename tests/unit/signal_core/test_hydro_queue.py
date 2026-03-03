"""
Tests for signal_core.core.hydro_ingress_queue.drain_queue

Invariants:
- Missing queue file → returns []
- Empty queue file → returns []
- drain_queue() reads and clears the file (single-drainer contract)
- Returns HydroPacket instances matching the written records
- max_items caps how many are drained; remainder is preserved in file
"""

from __future__ import annotations

import json

import signal_core.core.hydro_ingress_queue as queue_mod
from signal_core.core.hydro_ingress_queue import drain_queue
from signal_core.core.hydro_types import HydroPacket, GateResult

T_FIXED = 1_705_320_000.0


def _packet_dict(packet_id: str = "pkt-q-001") -> dict:
    return dict(
        t=T_FIXED,
        packet_id=packet_id,
        lane="system",
        domain="system",
        channel="cpu:util",
        value={"cpu_percent": 42.0},
        provenance={"source": "test"},
        rate=None,
        anomaly_flag=False,
        replay=False,
        phase=0.0,
    )


def test_drain_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(queue_mod, "QUEUE_PATH", tmp_path / "no_such.jsonl")
    assert drain_queue() == []


def test_drain_empty_file(tmp_path, monkeypatch):
    q = tmp_path / "queue.jsonl"
    q.write_text("", encoding="utf-8")
    monkeypatch.setattr(queue_mod, "QUEUE_PATH", q)
    assert drain_queue() == []


def test_drain_clears_file(tmp_path, monkeypatch):
    q = tmp_path / "queue.jsonl"
    q.write_text(json.dumps(_packet_dict()) + "\n", encoding="utf-8")
    monkeypatch.setattr(queue_mod, "QUEUE_PATH", q)

    packets = drain_queue()
    assert len(packets) == 1
    assert isinstance(packets[0], HydroPacket)
    assert q.read_text(encoding="utf-8") == ""


def test_drain_multiple_packets(tmp_path, monkeypatch):
    q = tmp_path / "queue.jsonl"
    lines = "\n".join(
        json.dumps(_packet_dict(packet_id=f"pkt-{i}")) for i in range(3)
    ) + "\n"
    q.write_text(lines, encoding="utf-8")
    monkeypatch.setattr(queue_mod, "QUEUE_PATH", q)

    packets = drain_queue()
    assert len(packets) == 3
    assert [p.packet_id for p in packets] == ["pkt-0", "pkt-1", "pkt-2"]


def test_drain_max_items_preserves_remainder(tmp_path, monkeypatch):
    q = tmp_path / "queue.jsonl"
    lines = "\n".join(
        json.dumps(_packet_dict(packet_id=f"pkt-{i}")) for i in range(5)
    ) + "\n"
    q.write_text(lines, encoding="utf-8")
    monkeypatch.setattr(queue_mod, "QUEUE_PATH", q)

    drained = drain_queue(max_items=2)
    assert len(drained) == 2
    assert [p.packet_id for p in drained] == ["pkt-0", "pkt-1"]

    # Remaining 3 are still in file
    remaining = drain_queue()
    assert len(remaining) == 3
    assert [p.packet_id for p in remaining] == ["pkt-2", "pkt-3", "pkt-4"]
