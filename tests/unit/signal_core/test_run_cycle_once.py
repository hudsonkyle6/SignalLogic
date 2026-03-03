"""
Tests for signal_core.core.run_cycle_once

Modules covered:
- observe_once    (delegates to sample_once)
- run_cycle_once  (observe → gate → enqueue → dispatch pipeline)

Invariants:
- observe_once returns a HydroPacket
- run_cycle_once does not raise on successful path
- run_cycle_once returns early after REJECT gate result (no dispatch)
- run_cycle_once calls dispatch for PASS/QUARANTINE packets
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from signal_core.core.hydro_types import (
    HydroPacket,
    GateResult,
    Route,
)


T_FIXED = 1705320000.0


def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id="pkt-run-001",
        lane="system",
        domain="core",
        channel="system_metrics",
        value={"cpu_percent": 5.0},
        provenance={"source": "test"},
        rate=0.05,
        anomaly_flag=False,
        replay=False,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _ingress_decision(result: GateResult = GateResult.PASS) -> MagicMock:
    d = MagicMock()
    d.gate_result = result
    return d


def _dispatch_decision() -> MagicMock:
    d = MagicMock()
    d.route = Route.MAIN
    d.pressure_class = "operational"
    d.rule_id = "D1_MAIN"
    return d


class TestObserveOnce:
    def test_returns_hydro_packet(self):
        from signal_core.core.run_cycle_once import observe_once

        pkt = observe_once()
        assert isinstance(pkt, HydroPacket)

    def test_delegates_to_sample_once(self, monkeypatch):
        from signal_core.core.run_cycle_once import observe_once
        import signal_core.core.run_cycle_once as mod

        fake_pkt = _packet()
        monkeypatch.setattr(mod, "sample_once", lambda: fake_pkt)
        result = observe_once()
        assert result is fake_pkt


class TestRunCycleOnce:
    def _run(self, gate_result: GateResult = GateResult.PASS):
        """Run run_cycle_once with all I/O mocked."""
        pkt = _packet()
        ingress = _ingress_decision(gate_result)
        dispatch_calls = []

        with (
            patch("signal_core.core.run_cycle_once.sample_once", return_value=pkt),
            patch(
                "signal_core.core.run_cycle_once.hydro_ingress_gate",
                return_value=ingress,
            ),
            patch(
                "signal_core.core.run_cycle_once.enqueue_if_admitted"
            ) as mock_enqueue,
            patch(
                "signal_core.core.run_cycle_once.dispatch",
                side_effect=lambda p, d: dispatch_calls.append((p, d)),
            ),
        ):
            from signal_core.core.run_cycle_once import run_cycle_once

            run_cycle_once()

        return dispatch_calls, mock_enqueue

    def test_pass_calls_dispatch(self):
        dispatch_calls, _ = self._run(GateResult.PASS)
        assert len(dispatch_calls) == 1

    def test_quarantine_calls_dispatch(self):
        dispatch_calls, _ = self._run(GateResult.QUARANTINE)
        assert len(dispatch_calls) == 1

    def test_reject_skips_dispatch(self):
        dispatch_calls, _ = self._run(GateResult.REJECT)
        assert len(dispatch_calls) == 0

    def test_enqueue_always_called(self):
        _, mock_enqueue = self._run(GateResult.PASS)
        mock_enqueue.assert_called_once()

    def test_enqueue_called_even_on_reject(self):
        _, mock_enqueue = self._run(GateResult.REJECT)
        mock_enqueue.assert_called_once()

    def test_does_not_raise(self):
        self._run(GateResult.PASS)  # should not raise
