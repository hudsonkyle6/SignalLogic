"""
Tests for signal_core.core.control_signal

Invariants:
- emit_control_signal appends one JSON line per call
- The record contains all expected fields
- route field matches the dispatch decision route value
- Multiple calls accumulate as separate lines
- Parent directories are created if absent
- Coherence is extracted from packet.value["coherence"]
- Packets without coherence in value emit coherence=None
- Files rotate daily: signals-YYYY-MM-DD.jsonl written inside CONTROL_DIR
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import pytest

import signal_core.core.control_signal as cs_mod
from signal_core.core.control_signal import emit_control_signal
from signal_core.core.hydro_types import HydroPacket, DispatchDecision, Route


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=1705320000.0,
        packet_id="pkt-ctrl-001",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.82},
        provenance={"source": "unit_test"},
        rate=None,
        anomaly_flag=False,
        replay=False,
        diurnal_phase=0.45,
        semi_diurnal_phase=0.30,
        long_wave_phase=0.12,
        seasonal_band="summer",
        pattern_confidence=0.9,
        forest_proximity=0.20,
        afterglow_decay=0.5,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _decision(**overrides) -> DispatchDecision:
    defaults = dict(
        route=Route.MAIN,
        rule_id="D1_MAIN_OPERATIONAL",
        pressure_class="operational",
        observe=False,
    )
    defaults.update(overrides)
    return DispatchDecision(**defaults)


def _find_signal_files(directory: Path) -> List[Path]:
    """Return all signals-*.jsonl files written by emit_control_signal."""
    return sorted(directory.glob("signals-*.jsonl"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmitControlSignal:
    def test_creates_file_on_first_emit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path / "control")

        emit_control_signal(_packet(), _decision())

        files = _find_signal_files(tmp_path / "control")
        assert len(files) == 1

    def test_appends_one_line_per_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(), _decision())

        [path] = _find_signal_files(tmp_path)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_multiple_calls_accumulate_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        for i in range(5):
            emit_control_signal(_packet(packet_id=f"pkt-{i}"), _decision())

        files = _find_signal_files(tmp_path)
        total_lines = sum(
            len(f.read_text(encoding="utf-8").strip().splitlines())
            for f in files
        )
        assert total_lines == 5

    def test_record_contains_required_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(), _decision())

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        expected_fields = [
            "ts", "packet_id", "t", "domain", "lane", "channel",
            "route", "rule_id", "pressure_class", "observe",
            "forest_proximity", "seasonal_band", "coherence", "diurnal_phase",
        ]
        for field in expected_fields:
            assert field in record, f"Missing field: {field}"

    def test_route_value_matches_decision(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(), _decision(route=Route.MAIN, rule_id="D1_MAIN_OPERATIONAL"))

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["route"] == "MAIN"
        assert record["rule_id"] == "D1_MAIN_OPERATIONAL"

    def test_coherence_extracted_from_value(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(value={"coherence": 0.77}), _decision())

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["coherence"] == pytest.approx(0.77)

    def test_missing_coherence_emits_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(value={"something_else": 1}), _decision())

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["coherence"] is None

    def test_ts_is_recent_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        before = time.time()
        emit_control_signal(_packet(), _decision())
        after = time.time()

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert before <= record["ts"] <= after + 1.0

    def test_creates_nested_parent_directory(self, tmp_path, monkeypatch):
        deep_dir = tmp_path / "a" / "b" / "c"
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", deep_dir)

        emit_control_signal(_packet(), _decision())

        assert len(_find_signal_files(deep_dir)) == 1

    def test_observe_flag_carried_through(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(), _decision(observe=True))

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["observe"] is True

    def test_packet_identity_fields_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(
            _packet(packet_id="pkt-xyz", domain="natural", channel="temperature"),
            _decision(),
        )

        [path] = _find_signal_files(tmp_path)
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["packet_id"] == "pkt-xyz"
        assert record["domain"] == "natural"
        assert record["channel"] == "temperature"

    def test_filename_contains_utc_date(self, tmp_path, monkeypatch):
        """File name should match signals-YYYY-MM-DD.jsonl."""
        monkeypatch.setattr(cs_mod, "CONTROL_DIR", tmp_path)

        emit_control_signal(_packet(), _decision())

        [path] = _find_signal_files(tmp_path)
        assert path.name.startswith("signals-")
        assert path.suffix == ".jsonl"
        # Date portion must be parseable
        date_part = path.stem[len("signals-"):]
        from datetime import date
        date.fromisoformat(date_part)  # raises ValueError if malformed
