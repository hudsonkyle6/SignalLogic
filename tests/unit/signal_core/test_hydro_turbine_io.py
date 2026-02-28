"""
Tests for signal_core.core.hydro_turbine — I/O and process_turbine paths.

Invariants:
- _load_recent_turbine returns [] when turbine dir is absent or empty
- _load_recent_turbine skips malformed JSONL lines
- _load_recent_turbine respects max_records limit
- _append_observation writes a valid JSON line to the daily basin file
- process_turbine uses pre-stamped phases from packet when present
- process_turbine falls back to compute_anchor when phases are absent
- _assess_convergence skips history records with missing/bad diurnal_phase
"""
from __future__ import annotations

import json
import time
import pytest

import signal_core.core.hydro_turbine as turbine_mod
from signal_core.core.hydro_turbine import (
    TurbineObservation,
    _load_recent_turbine,
    _append_observation,
    _assess_convergence,
    process_turbine,
    CONVERGENCE_WINDOW,
)
from signal_core.core.hydro_types import HydroPacket
from rhythm_os.runtime.temporal_anchor import compute_anchor

T_FIXED = 1705320000.0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id="pkt-test-001",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.5},
        provenance={"source": "unit_test"},
        rate=None,
        anomaly_flag=False,
        replay=False,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _make_obs(domain: str = "system", aligned_domains=None, note: str = "isolated") -> TurbineObservation:
    anchor = compute_anchor(T_FIXED, domain=domain)
    return TurbineObservation(
        t=T_FIXED,
        packet_id="pkt-test-001",
        domain=domain,
        lane="system",
        route_reason="D3_TURBINE_EXPLORATORY",
        diurnal_phase=anchor.diurnal_phase,
        semi_diurnal_phase=anchor.semi_diurnal_phase,
        long_wave_phase=anchor.long_wave_phase,
        dominant_hz=anchor.dominant_hz,
        aligned_domains=aligned_domains or [],
        convergence_note=note,
    )


# ------------------------------------------------------------------
# _load_recent_turbine
# ------------------------------------------------------------------

class TestLoadRecentTurbine:
    def test_returns_empty_when_dir_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path / "no_such_dir")
        assert _load_recent_turbine() == []

    def test_returns_empty_when_dir_is_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        assert _load_recent_turbine() == []

    def test_loads_records_from_jsonl(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        f = tmp_path / "2024-01-01.jsonl"
        record = {"domain": "system", "diurnal_phase": 0.3}
        f.write_text(json.dumps(record) + "\n", encoding="utf-8")
        result = _load_recent_turbine()
        assert len(result) == 1
        assert result[0]["domain"] == "system"

    def test_skips_malformed_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        f = tmp_path / "2024-01-01.jsonl"
        good = json.dumps({"domain": "natural", "diurnal_phase": 0.5})
        f.write_text("NOT_VALID_JSON\n" + good + "\n", encoding="utf-8")
        result = _load_recent_turbine()
        assert len(result) == 1
        assert result[0]["domain"] == "natural"

    def test_skips_blank_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        f = tmp_path / "2024-01-01.jsonl"
        good = json.dumps({"domain": "cyber", "diurnal_phase": 0.1})
        f.write_text("\n\n" + good + "\n\n", encoding="utf-8")
        result = _load_recent_turbine()
        assert len(result) == 1

    def test_respects_max_records(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        f = tmp_path / "2024-01-01.jsonl"
        lines = [json.dumps({"domain": "system", "diurnal_phase": i / 100}) for i in range(20)]
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = _load_recent_turbine(max_records=5)
        assert len(result) == 5

    def test_loads_across_multiple_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        for date, domain in [("2024-01-01", "natural"), ("2024-01-02", "market")]:
            f = tmp_path / f"{date}.jsonl"
            f.write_text(json.dumps({"domain": domain, "diurnal_phase": 0.2}) + "\n")
        result = _load_recent_turbine()
        domains = {r["domain"] for r in result}
        assert "natural" in domains or "market" in domains  # at least one file loaded

    def test_skips_unreadable_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        # Create a readable file alongside an unreadable one
        good = tmp_path / "2024-01-02.jsonl"
        good.write_text(json.dumps({"domain": "system", "diurnal_phase": 0.2}) + "\n")

        bad = tmp_path / "2024-01-01.jsonl"
        bad.write_text("placeholder")

        # Patch Path.read_text to raise for the bad file
        original_read_text = bad.__class__.read_text

        def patched_read_text(self, *args, **kwargs):
            if self.name == bad.name:
                raise OSError("simulated read error")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(bad.__class__, "read_text", patched_read_text)

        # Should not raise; bad file is skipped, good file is loaded
        result = _load_recent_turbine()
        assert any(r.get("domain") == "system" for r in result)


# ------------------------------------------------------------------
# _append_observation
# ------------------------------------------------------------------

class TestAppendObservation:
    def test_creates_file_and_appends_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        obs = _make_obs()
        _append_observation(obs)

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["packet_id"] == "pkt-test-001"
        assert record["domain"] == "system"
        assert "aligned_domains" in record
        assert "convergence_note" in record

    def test_appends_multiple_observations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        obs1 = _make_obs(domain="system")
        obs2 = _make_obs(domain="natural")
        _append_observation(obs1)
        _append_observation(obs2)

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_creates_parent_directory_if_missing(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "nested"
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", nested)
        obs = _make_obs()
        _append_observation(obs)
        files = list(nested.glob("*.jsonl"))
        assert len(files) == 1


# ------------------------------------------------------------------
# _assess_convergence — malformed history records
# ------------------------------------------------------------------

class TestAssessConvergenceMalformed:
    def test_skips_record_with_missing_diurnal_phase(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        # A record with no diurnal_phase key — should be silently skipped
        history = [{"domain": "natural"}]  # missing diurnal_phase
        domains, note = _assess_convergence(anchor, "system", history)
        assert domains == []
        assert note == "isolated"

    def test_skips_record_with_non_numeric_diurnal_phase(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        history = [{"domain": "natural", "diurnal_phase": "not-a-number"}]
        domains, note = _assess_convergence(anchor, "system", history)
        assert domains == []
        assert note == "isolated"

    def test_skips_record_with_none_diurnal_phase(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        history = [{"domain": "natural", "diurnal_phase": None}]
        domains, note = _assess_convergence(anchor, "system", history)
        assert domains == []
        assert note == "isolated"

    def test_good_record_after_malformed_still_converges(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        nearby = (anchor.diurnal_phase + CONVERGENCE_WINDOW * 0.5) % 1.0
        history = [
            {"domain": "market", "diurnal_phase": "bad"},
            {"domain": "natural", "diurnal_phase": nearby},
        ]
        domains, note = _assess_convergence(anchor, "system", history)
        assert "natural" in domains


# ------------------------------------------------------------------
# process_turbine
# ------------------------------------------------------------------

class TestProcessTurbine:
    def test_uses_prestamped_phases_from_packet(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        monkeypatch.setattr(turbine_mod, "_load_recent_turbine", lambda **_: [])

        anchor = compute_anchor(T_FIXED, domain="system")
        packet = _make_packet(
            diurnal_phase=anchor.diurnal_phase,
            semi_diurnal_phase=anchor.semi_diurnal_phase,
            long_wave_phase=anchor.long_wave_phase,
        )
        obs = process_turbine(packet, route_reason="D3_TURBINE_EXPLORATORY")

        assert isinstance(obs, TurbineObservation)
        assert obs.diurnal_phase == pytest.approx(anchor.diurnal_phase)
        assert obs.packet_id == "pkt-test-001"
        assert obs.route_reason == "D3_TURBINE_EXPLORATORY"

    def test_falls_back_to_compute_anchor_when_phases_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        monkeypatch.setattr(turbine_mod, "_load_recent_turbine", lambda **_: [])

        packet = _make_packet()  # no diurnal/semi/long phases
        obs = process_turbine(packet, route_reason="D4_SAFE_FALLBACK")

        expected = compute_anchor(T_FIXED, domain="system")
        assert obs.diurnal_phase == pytest.approx(expected.diurnal_phase)
        assert obs.route_reason == "D4_SAFE_FALLBACK"

    def test_process_turbine_appends_to_basin(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        monkeypatch.setattr(turbine_mod, "_load_recent_turbine", lambda **_: [])

        packet = _make_packet()
        process_turbine(packet, route_reason="D3_TURBINE_EXPLORATORY")

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        record = json.loads(files[0].read_text().strip())
        assert record["packet_id"] == "pkt-test-001"

    def test_process_turbine_with_converging_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)

        anchor = compute_anchor(T_FIXED, domain="system")
        nearby = (anchor.diurnal_phase + CONVERGENCE_WINDOW * 0.5) % 1.0
        fake_history = [{"domain": "natural", "diurnal_phase": nearby}]
        monkeypatch.setattr(turbine_mod, "_load_recent_turbine", lambda **_: fake_history)

        packet = _make_packet()
        obs = process_turbine(packet, route_reason="D3_TURBINE_EXPLORATORY")
        assert "natural" in obs.aligned_domains

    def test_observation_fields_complete(self, tmp_path, monkeypatch):
        monkeypatch.setattr(turbine_mod, "TURBINE_DIR", tmp_path)
        monkeypatch.setattr(turbine_mod, "_load_recent_turbine", lambda **_: [])

        packet = _make_packet(domain="market", lane="market")
        obs = process_turbine(packet, route_reason="D3_TURBINE_EXPLORATORY")

        assert obs.domain == "market"
        assert obs.lane == "market"
        assert isinstance(obs.aligned_domains, list)
        assert isinstance(obs.convergence_note, str)
        assert isinstance(obs.dominant_hz, float)
