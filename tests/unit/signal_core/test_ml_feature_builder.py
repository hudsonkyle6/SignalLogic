"""
Tests for signal_core.core.ml.feature_builder

Invariants:
- _scar_features_for_domain returns zero-dict when no file exists
- _scar_features_for_domain returns zero-dict when file is empty
- _scar_features_for_domain skips corrupt JSON lines without crashing
- _scar_features_for_domain computes correct aggregates from valid scars
- _all_scar_features returns empty dict when SCARS_DIR does not exist
- _all_scar_features covers all domain files present in SCARS_DIR
- _convergence_features returns zero-dict when summary is None
- _convergence_features returns zero-dict when convergence_events is empty
- _convergence_features extracts dominant_phase from highest-domain-count event
- _temporal_features produces diurnal_phase in [0, 1) and correct hour/day/month
- _readiness_features returns False/zero when baseline_status is None
- _readiness_features mirrors ReadinessStatus fields
- extract_features produces a flat, JSON-serialisable dict
- append_features creates the file and writes valid JSON
- extract_and_append combines extraction and persistence end-to-end
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import signal_core.core.ml.feature_builder as fb_mod
from signal_core.core.ml.feature_builder import (
    _all_scar_features,
    _convergence_features,
    _readiness_features,
    _scar_features_for_domain,
    _temporal_features,
    append_features,
    extract_and_append,
    extract_features,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_scar_lines(path: Path, scars: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for s in scars:
            f.write(json.dumps(s) + "\n")


def _make_scar_dict(
    domain: str = "system",
    pressure: float = 1.0,
    reinforcement_count: int = 3,
    ever_changed: bool = True,
    trigger: str = "forest_proximity",
) -> dict:
    return {
        "scar_id": "abc123",
        "domain": domain,
        "pattern_key": "summer:net_pressure",
        "pressure": pressure,
        "changed": False,
        "ever_changed": ever_changed,
        "trigger": trigger,
        "first_seen": time.time() - 3600,
        "last_reinforced": time.time(),
        "last_decayed": time.time(),
        "decay_rate": 0.05,
        "reinforcement_count": reinforcement_count,
    }


@dataclass
class _FakeReadiness:
    system_ready: bool
    natural_ready: bool
    system_count: int
    natural_count: int


@dataclass
class _FakeCycleResult:
    cycle_ts: float = 0.0
    packets_drained: int = 0
    rejected: int = 0
    committed: int = 0
    turbine_obs: int = 0
    spillway_quarantined: int = 0
    spillway_hold: int = 0
    convergence_summary: Optional[Dict[str, Any]] = None
    baseline_status: Optional[Any] = None


# ---------------------------------------------------------------------------
# _scar_features_for_domain
# ---------------------------------------------------------------------------


class TestScarFeaturesForDomain:
    def test_no_file_returns_zero_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        result = _scar_features_for_domain("system")
        assert result["scar_system_count"] == 0
        assert result["scar_system_max_pressure"] == 0.0

    def test_empty_file_returns_zero_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        (tmp_path / "system.jsonl").write_text("")
        result = _scar_features_for_domain("system")
        assert result["scar_system_count"] == 0

    def test_corrupt_lines_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        path = tmp_path / "system.jsonl"
        path.write_text("not-json\n" + json.dumps(_make_scar_dict()) + "\n{broken\n")
        result = _scar_features_for_domain("system")
        # One valid scar survives
        assert result["scar_system_count"] == 1

    def test_single_scar_aggregates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        scar = _make_scar_dict(pressure=1.2, reinforcement_count=5, ever_changed=True)
        _write_scar_lines(tmp_path / "system.jsonl", [scar])
        result = _scar_features_for_domain("system")
        assert result["scar_system_count"] == 1
        assert result["scar_system_max_pressure"] == 1.2
        assert result["scar_system_avg_pressure"] == 1.2
        assert result["scar_system_ever_changed_count"] == 1
        assert result["scar_system_avg_reinforcements"] == 5.0

    def test_multiple_scars_aggregates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        s1 = _make_scar_dict(pressure=0.4, reinforcement_count=2, ever_changed=False)
        s2 = _make_scar_dict(
            pressure=1.6, reinforcement_count=8, ever_changed=True, trigger="compound"
        )
        _write_scar_lines(tmp_path / "system.jsonl", [s1, s2])
        result = _scar_features_for_domain("system")
        assert result["scar_system_count"] == 2
        assert result["scar_system_max_pressure"] == 1.6
        assert result["scar_system_avg_pressure"] == round((0.4 + 1.6) / 2, 4)
        assert result["scar_system_ever_changed_count"] == 1
        assert result["scar_system_compound_count"] == 1
        assert result["scar_system_avg_reinforcements"] == 5.0

    def test_prefix_uses_domain_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        scar = _make_scar_dict(domain="natural", pressure=0.5)
        _write_scar_lines(tmp_path / "natural.jsonl", [scar])
        result = _scar_features_for_domain("natural")
        assert "scar_natural_count" in result
        assert "scar_system_count" not in result


# ---------------------------------------------------------------------------
# _all_scar_features
# ---------------------------------------------------------------------------


class TestAllScarFeatures:
    def test_missing_scars_dir_returns_empty(self, tmp_path, monkeypatch):
        missing = tmp_path / "no_scars_here"
        monkeypatch.setattr(fb_mod, "SCARS_DIR", missing)
        assert _all_scar_features() == {}

    def test_covers_all_domain_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        for domain in ("system", "natural", "market"):
            scar = _make_scar_dict(domain=domain, pressure=0.3)
            scar["scar_id"] = domain  # unique id per domain
            _write_scar_lines(tmp_path / f"{domain}.jsonl", [scar])
        result = _all_scar_features()
        assert "scar_system_count" in result
        assert "scar_natural_count" in result
        assert "scar_market_count" in result

    def test_empty_scars_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        assert _all_scar_features() == {}


# ---------------------------------------------------------------------------
# _convergence_features
# ---------------------------------------------------------------------------


class TestConvergenceFeatures:
    def test_none_returns_zero_dict(self):
        result = _convergence_features(None)
        assert result["convergence_event_count"] == 0
        assert result["has_convergence"] is False
        assert result["dominant_phase"] == 0.0

    def test_empty_events_list(self):
        summary = {
            "convergence_event_count": 0,
            "strong_events": 0,
            "total_turbine_observations": 5,
            "domains_observed": {"system": 3, "natural": 2},
            "convergence_events": [],
        }
        result = _convergence_features(summary)
        assert result["convergence_event_count"] == 0
        assert result["has_convergence"] is False
        assert result["turbine_domain_count"] == 2
        assert result["total_turbine_obs"] == 5

    def test_dominant_phase_from_highest_domain_count(self):
        summary = {
            "convergence_event_count": 2,
            "strong_events": 1,
            "total_turbine_observations": 20,
            "domains_observed": {"system": 8, "natural": 7, "market": 5},
            "convergence_events": [
                {
                    "diurnal_phase": 0.25,
                    "domains": ["system", "natural"],
                    "domain_count": 2,
                    "strength": "weak",
                },
                {
                    "diurnal_phase": 0.75,
                    "domains": ["system", "natural", "market"],
                    "domain_count": 3,
                    "strength": "strong",
                },
            ],
        }
        result = _convergence_features(summary)
        assert result["dominant_phase"] == 0.75  # 3-domain event wins
        assert result["max_event_domain_count"] == 3
        assert result["strong_events"] == 1
        assert result["has_convergence"] is True
        assert result["turbine_domain_count"] == 3


# ---------------------------------------------------------------------------
# _temporal_features
# ---------------------------------------------------------------------------


class TestTemporalFeatures:
    def test_diurnal_phase_in_range(self):
        result = _temporal_features(time.time())
        assert 0.0 <= result["diurnal_phase"] < 1.0

    def test_hour_in_range(self):
        result = _temporal_features(time.time())
        assert 0 <= result["hour_of_day"] <= 23

    def test_day_of_week_in_range(self):
        result = _temporal_features(time.time())
        assert 0 <= result["day_of_week"] <= 6

    def test_month_in_range(self):
        result = _temporal_features(time.time())
        assert 1 <= result["month"] <= 12

    def test_midnight_utc_gives_phase_zero(self):
        # 2024-01-15 00:00:00 UTC
        midnight_utc = 1705276800.0
        result = _temporal_features(midnight_utc)
        assert result["diurnal_phase"] == 0.0
        assert result["hour_of_day"] == 0

    def test_noon_utc_gives_phase_half(self):
        # 2024-01-15 12:00:00 UTC
        noon_utc = 1705320000.0
        result = _temporal_features(noon_utc)
        assert abs(result["diurnal_phase"] - 0.5) < 0.001


# ---------------------------------------------------------------------------
# _readiness_features
# ---------------------------------------------------------------------------


class TestReadinessFeatures:
    def test_none_returns_false_zeros(self):
        result = _readiness_features(None)
        assert result["system_ready"] is False
        assert result["natural_ready"] is False
        assert result["system_count"] == 0
        assert result["natural_count"] == 0

    def test_mirrors_status_fields(self):
        status = _FakeReadiness(
            system_ready=True, natural_ready=False, system_count=45, natural_count=2
        )
        result = _readiness_features(status)
        assert result["system_ready"] is True
        assert result["natural_ready"] is False
        assert result["system_count"] == 45
        assert result["natural_count"] == 2


# ---------------------------------------------------------------------------
# extract_features
# ---------------------------------------------------------------------------


class TestExtractFeatures:
    def test_returns_flat_json_serialisable_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        result_obj = _FakeCycleResult(
            cycle_ts=time.time(),
            packets_drained=3,
            committed=3,
            baseline_status=_FakeReadiness(True, True, 40, 6),
        )
        features = extract_features(result_obj)
        # Must round-trip through JSON without error
        raw = json.dumps(features)
        parsed = json.loads(raw)
        assert parsed["packets_drained"] == 3
        assert parsed["committed"] == 3
        assert "ts" in parsed
        assert "diurnal_phase" in parsed

    def test_cycle_stats_all_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        result_obj = _FakeCycleResult(
            cycle_ts=time.time(),
            packets_drained=5,
            rejected=1,
            committed=4,
            turbine_obs=12,
            spillway_quarantined=0,
            spillway_hold=1,
        )
        features = extract_features(result_obj)
        assert features["packets_drained"] == 5
        assert features["rejected"] == 1
        assert features["committed"] == 4
        assert features["turbine_obs"] == 12
        assert features["spillway_hold"] == 1

    def test_scar_features_included_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        scar = _make_scar_dict(domain="system", pressure=0.9)
        _write_scar_lines(tmp_path / "system.jsonl", [scar])
        result_obj = _FakeCycleResult(cycle_ts=time.time())
        features = extract_features(result_obj)
        assert "scar_system_count" in features
        assert features["scar_system_count"] == 1

    def test_uses_current_time_when_cycle_ts_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path)
        obj = MagicMock(spec=[])  # no cycle_ts attribute
        before = time.time()
        features = extract_features(obj)
        after = time.time()
        assert before <= features["ts"] <= after


# ---------------------------------------------------------------------------
# append_features / extract_and_append
# ---------------------------------------------------------------------------


class TestAppendAndExtract:
    def test_append_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "ML_DIR", tmp_path)
        monkeypatch.setattr(fb_mod, "_FEATURES_PATH", tmp_path / "features.jsonl")
        append_features({"ts": 1.0, "x": 2})
        assert (tmp_path / "features.jsonl").exists()

    def test_append_writes_valid_json_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "ML_DIR", tmp_path)
        monkeypatch.setattr(fb_mod, "_FEATURES_PATH", tmp_path / "features.jsonl")
        append_features({"ts": 123.0, "convergence_event_count": 2})
        line = (tmp_path / "features.jsonl").read_text().strip()
        parsed = json.loads(line)
        assert parsed["convergence_event_count"] == 2

    def test_append_accumulates_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "ML_DIR", tmp_path)
        monkeypatch.setattr(fb_mod, "_FEATURES_PATH", tmp_path / "features.jsonl")
        for i in range(3):
            append_features({"ts": float(i)})
        lines = (tmp_path / "features.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_extract_and_append_end_to_end(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb_mod, "SCARS_DIR", tmp_path / "scars")
        monkeypatch.setattr(fb_mod, "ML_DIR", tmp_path / "ml")
        monkeypatch.setattr(
            fb_mod, "_FEATURES_PATH", tmp_path / "ml" / "features.jsonl"
        )
        result_obj = _FakeCycleResult(
            cycle_ts=time.time(),
            packets_drained=2,
            committed=2,
            baseline_status=_FakeReadiness(True, False, 35, 1),
            convergence_summary={
                "convergence_event_count": 1,
                "strong_events": 0,
                "total_turbine_observations": 8,
                "domains_observed": {"system": 5, "natural": 3},
                "convergence_events": [
                    {
                        "diurnal_phase": 0.33,
                        "domains": ["system", "natural"],
                        "domain_count": 2,
                        "strength": "weak",
                    }
                ],
            },
        )
        features = extract_and_append(result_obj)
        assert features["convergence_event_count"] == 1
        assert features["system_ready"] is True
        assert features["packets_drained"] == 2

        # File was written
        lines = (tmp_path / "ml" / "features.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["convergence_event_count"] == 1
