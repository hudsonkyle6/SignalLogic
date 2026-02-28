"""
Tests for signal_core.core.hydro_turbine_summary

Invariants:
- build_summary returns correct field structure for empty and non-empty records
- _find_convergence_events detects weak and strong convergence
- _find_convergence_events ignores same-domain pairs
- _phase_bucket quantises correctly
- run_turbine_summary always appends — no once-per-day dedup guard
- run_turbine_summary returns a dict with expected keys
- Multiple run_turbine_summary calls in one day produce multiple summary lines
"""
from __future__ import annotations

import json
import pytest

import signal_core.core.hydro_turbine_summary as ts_mod
from signal_core.core.hydro_turbine_summary import (
    build_summary,
    run_turbine_summary,
    _find_convergence_events,
    _phase_bucket,
    CONVERGENCE_WINDOW,
)


# ---------------------------------------------------------------------------
# _phase_bucket
# ---------------------------------------------------------------------------

class TestPhaseBucket:
    def test_zero_maps_to_zero(self):
        assert _phase_bucket(0.0) == 0

    def test_full_cycle_wraps(self):
        assert _phase_bucket(1.0) == 0  # 1.0 * 12 % 12 == 0

    def test_midpoint(self):
        assert _phase_bucket(0.5) == 6

    def test_near_end(self):
        assert _phase_bucket(0.99) == 11


# ---------------------------------------------------------------------------
# _find_convergence_events
# ---------------------------------------------------------------------------

def _rec(domain: str, phase: float) -> dict:
    return {"domain": domain, "diurnal_phase": phase}


class TestFindConvergenceEvents:
    def test_empty_records(self):
        assert _find_convergence_events([]) == []

    def test_single_domain_no_convergence(self):
        records = [_rec("system", 0.3), _rec("system", 0.31)]
        events = _find_convergence_events(records)
        assert events == []

    def test_two_domains_within_window(self):
        phase = 0.5
        records = [
            _rec("system", phase),
            _rec("natural", phase + CONVERGENCE_WINDOW * 0.5),
        ]
        events = _find_convergence_events(records)
        assert len(events) == 1
        assert events[0]["strength"] == "weak"
        assert set(events[0]["domains"]) == {"system", "natural"}

    def test_three_domains_strong(self):
        phase = 0.5
        records = [
            _rec("system", phase),
            _rec("natural", phase + 0.01),
            _rec("market", phase + 0.02),
        ]
        events = _find_convergence_events(records)
        strong = [e for e in events if e["strength"] == "strong"]
        assert len(strong) >= 1
        assert events[0]["domain_count"] >= 3

    def test_far_apart_domains_no_convergence(self):
        records = [
            _rec("system", 0.1),
            _rec("natural", 0.6),
        ]
        events = _find_convergence_events(records)
        assert events == []


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------

class TestBuildSummary:
    def test_empty_records(self):
        s = build_summary([])
        assert s["total_turbine_observations"] == 0
        assert s["convergence_event_count"] == 0
        assert s["strong_events"] == 0
        assert s["domains_observed"] == {}
        assert "ts" in s
        assert "date" in s

    def test_counts_domains(self):
        records = [
            {"domain": "system", "diurnal_phase": 0.5},
            {"domain": "natural", "diurnal_phase": 0.5},
            {"domain": "system", "diurnal_phase": 0.6},
        ]
        s = build_summary(records)
        assert s["total_turbine_observations"] == 3
        assert s["domains_observed"]["system"] == 2
        assert s["domains_observed"]["natural"] == 1

    def test_convergence_events_populated(self):
        phase = 0.5
        records = [
            {"domain": "system", "diurnal_phase": phase},
            {"domain": "natural", "diurnal_phase": phase + 0.01},
        ]
        s = build_summary(records)
        assert s["convergence_event_count"] >= 1


# ---------------------------------------------------------------------------
# run_turbine_summary — always appends (no dedup guard)
# ---------------------------------------------------------------------------

class TestRunTurbineSummaryAlwaysAppends:
    def test_first_call_appends_summary(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        summary_path = tmp_path / "summary.jsonl"
        run_turbine_summary()

        assert summary_path.exists()
        lines = summary_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_second_call_also_appends(self, tmp_path, monkeypatch):
        """
        In loop mode the summary is written on every cycle.
        Two calls must produce two lines — no once-per-day dedup.
        """
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        run_turbine_summary()
        run_turbine_summary()

        summary_path = tmp_path / "summary.jsonl"
        lines = summary_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_ten_calls_produce_ten_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        for _ in range(10):
            run_turbine_summary()

        summary_path = tmp_path / "summary.jsonl"
        lines = summary_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 10

    def test_return_value_has_required_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        result = run_turbine_summary()

        for key in [
            "ts", "date", "total_turbine_observations",
            "domains_observed", "convergence_events",
            "convergence_event_count", "strong_events",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_summary_line_is_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        run_turbine_summary()

        summary_path = tmp_path / "summary.jsonl"
        line = summary_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert "date" in record

    def test_reads_existing_turbine_observations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts_mod, "TURBINE_DIR", tmp_path)

        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        obs_file = tmp_path / f"{today}.jsonl"
        obs_file.write_text(
            json.dumps({"domain": "system", "diurnal_phase": 0.3}) + "\n"
            + json.dumps({"domain": "natural", "diurnal_phase": 0.32}) + "\n",
            encoding="utf-8",
        )

        result = run_turbine_summary()

        assert result["total_turbine_observations"] == 2
        assert "system" in result["domains_observed"]
        assert "natural" in result["domains_observed"]
