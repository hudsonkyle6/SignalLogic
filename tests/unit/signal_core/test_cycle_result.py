"""
Tests for signal_core.core.hydro_run_cadence — CycleResult wiring

Invariants:
- main() always returns a CycleResult (not None)
- CycleResult has all expected fields
- Empty queue → committed=0, turbine_obs=0, rejected=0
- CycleResult.cycle_ts is a float timestamp
- CycleResult.convergence_summary is a dict (even for empty cycles)
- Counts are non-negative
- run_full_cycle() calls run_cycle_once() then main()
"""

from __future__ import annotations

import time

import signal_core.core.hydro_run_cadence as cadence_mod
import signal_core.core.hydro_run as run_mod
from signal_core.core.hydro_run_cadence import CycleResult, main
from signal_core.core.hydro_run import run_full_cycle


# ------------------------------------------------------------------
# CycleResult dataclass
# ------------------------------------------------------------------


class TestCycleResultStructure:
    def test_has_cycle_ts(self):
        r = CycleResult(
            cycle_ts=1.0,
            packets_drained=0,
            rejected=0,
            committed=0,
            turbine_obs=0,
            spillway_quarantined=0,
            spillway_hold=0,
        )
        assert r.cycle_ts == 1.0

    def test_convergence_summary_defaults_none(self):
        r = CycleResult(
            cycle_ts=1.0,
            packets_drained=0,
            rejected=0,
            committed=0,
            turbine_obs=0,
            spillway_quarantined=0,
            spillway_hold=0,
        )
        assert r.convergence_summary is None

    def test_all_count_fields_present(self):
        r = CycleResult(
            cycle_ts=1.0,
            packets_drained=5,
            rejected=1,
            committed=3,
            turbine_obs=2,
            spillway_quarantined=1,
            spillway_hold=0,
        )
        assert r.packets_drained == 5
        assert r.rejected == 1
        assert r.committed == 3
        assert r.turbine_obs == 2
        assert r.spillway_quarantined == 1
        assert r.spillway_hold == 0


# ------------------------------------------------------------------
# main() with empty queue
# ------------------------------------------------------------------


class TestMainEmptyQueue:
    def test_returns_cycle_result(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(
            cadence_mod,
            "run_turbine_summary",
            lambda: {"total_turbine_observations": 0},
        )
        result = main()
        assert isinstance(result, CycleResult)

    def test_empty_queue_zero_committed(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        result = main()
        assert result.committed == 0

    def test_empty_queue_zero_drained(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        result = main()
        assert result.packets_drained == 0

    def test_empty_queue_zero_turbine_obs(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        result = main()
        assert result.turbine_obs == 0

    def test_empty_queue_zero_rejected(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        result = main()
        assert result.rejected == 0

    def test_cycle_ts_is_float(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        result = main()
        assert isinstance(result.cycle_ts, float)

    def test_cycle_ts_is_recent(self, monkeypatch):
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: {})
        before = time.time()
        result = main()
        after = time.time()
        assert before <= result.cycle_ts <= after

    def test_turbine_summary_always_called(self, monkeypatch):
        called = []
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(
            cadence_mod, "run_turbine_summary", lambda: called.append(1) or {}
        )
        main()
        assert len(called) == 1

    def test_convergence_summary_stored(self, monkeypatch):
        summary = {"convergence_event_count": 2, "strong_events": 1}
        monkeypatch.setattr(cadence_mod, "drain_queue", lambda: [])
        monkeypatch.setattr(cadence_mod, "run_turbine_summary", lambda: summary)
        result = main()
        assert result.convergence_summary == summary


# ------------------------------------------------------------------
# run_full_cycle() calls both components
# ------------------------------------------------------------------


class TestRunFullCycle:
    def test_returns_cycle_result(self, monkeypatch):
        monkeypatch.setattr(run_mod, "run_cycle_once", lambda: None)
        monkeypatch.setattr(
            run_mod,
            "_hydro_daily",
            lambda: CycleResult(
                cycle_ts=1.0,
                packets_drained=0,
                rejected=0,
                committed=0,
                turbine_obs=0,
                spillway_quarantined=0,
                spillway_hold=0,
            ),
        )
        result = run_full_cycle()
        assert isinstance(result, CycleResult)

    def test_calls_run_cycle_once(self, monkeypatch):
        calls = []
        monkeypatch.setattr(run_mod, "run_cycle_once", lambda: calls.append("observe"))
        monkeypatch.setattr(
            run_mod,
            "_hydro_daily",
            lambda: CycleResult(
                cycle_ts=1.0,
                packets_drained=1,
                rejected=0,
                committed=1,
                turbine_obs=0,
                spillway_quarantined=0,
                spillway_hold=0,
            ),
        )
        run_full_cycle()
        assert "observe" in calls

    def test_calls_hydro_daily(self, monkeypatch):
        calls = []
        monkeypatch.setattr(run_mod, "run_cycle_once", lambda: None)
        expected = CycleResult(
            cycle_ts=1.0,
            packets_drained=1,
            rejected=0,
            committed=1,
            turbine_obs=0,
            spillway_quarantined=0,
            spillway_hold=0,
        )
        monkeypatch.setattr(
            run_mod, "_hydro_daily", lambda: calls.append("daily") or expected
        )
        result = run_full_cycle()
        assert "daily" in calls
        # run_full_cycle attaches baseline_status via dataclasses.replace(),
        # so result is a new object — check core fields match instead of identity
        assert result.cycle_ts == expected.cycle_ts
        assert result.committed == expected.committed
        assert result.packets_drained == expected.packets_drained

    def test_observe_runs_before_drain(self, monkeypatch):
        order = []
        monkeypatch.setattr(run_mod, "run_cycle_once", lambda: order.append(1))
        monkeypatch.setattr(
            run_mod,
            "_hydro_daily",
            lambda: (
                order.append(2)
                or CycleResult(
                    cycle_ts=1.0,
                    packets_drained=0,
                    rejected=0,
                    committed=0,
                    turbine_obs=0,
                    spillway_quarantined=0,
                    spillway_hold=0,
                )
            ),
        )
        run_full_cycle()
        assert order == [1, 2]
