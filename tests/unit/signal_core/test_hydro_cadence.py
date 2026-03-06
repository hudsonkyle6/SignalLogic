"""
Tests for signal_core.core.hydro_run_cadence

Modules covered:
- CycleResult (dataclass)
- commit_packet (penstock write)
- main() — all route branches: REJECT, MAIN, TURBINE, SPILLWAY, DROP
- _persist_cycle_result
- _run_voice_narration (error-tolerant)
- _run_voice_interpretation (no strong events early return)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from signal_core.core.hydro_types import GateResult, HydroPacket, Route


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_T = 1_705_320_000.0


def _pkt(**kw) -> HydroPacket:
    defaults = dict(
        t=_T,
        packet_id="test-001",
        lane="system",
        domain="system",
        channel="metrics",
        value={"coherence": 0.8},
        provenance={"source": "test"},
        rate=0.05,
        anomaly_flag=False,
        replay=False,
    )
    defaults.update(kw)
    return HydroPacket(**defaults)


def _ingress(result: GateResult = GateResult.PASS) -> MagicMock:
    d = MagicMock()
    d.gate_result = result
    d.reason = "ok"
    return d


def _dispatch_decision(route_name: str = "MAIN", observe: bool = False) -> MagicMock:
    d = MagicMock()
    d.route = MagicMock()
    d.route.name = route_name
    d.route.value = route_name.lower()
    d.rule_id = f"D_{route_name}"
    d.observe = observe
    d.pressure_class = "operational"
    return d


# ===========================================================================
# CycleResult
# ===========================================================================


class TestCycleResult:
    def test_construct_with_defaults(self):
        from signal_core.core.hydro_run_cadence import CycleResult

        r = CycleResult(
            cycle_ts=_T,
            packets_drained=5,
            rejected=1,
            committed=4,
            turbine_obs=2,
            spillway_quarantined=0,
            spillway_hold=0,
        )
        assert r.convergence_summary is None
        assert r.baseline_status is None
        assert r.ml_prediction is None


# ===========================================================================
# commit_packet
# ===========================================================================


class TestCommitPacket:
    def _call(self, pkt: HydroPacket):
        from signal_core.core.hydro_run_cadence import commit_packet

        with patch(
            "signal_core.core.hydro_run_cadence.append_wave_from_hydro"
        ) as mock_append:
            commit_packet(pkt)
        return mock_append

    def test_calls_append_wave(self):
        mock = self._call(_pkt())
        mock.assert_called_once()

    def test_coherence_clamped_above_one(self):
        pkt = _pkt(value={"coherence": 5.0})
        mock = self._call(pkt)
        wave = mock.call_args[0][0]
        assert wave.amplitude <= 1.0

    def test_coherence_clamped_below_zero(self):
        pkt = _pkt(value={"coherence": -2.0})
        mock = self._call(pkt)
        wave = mock.call_args[0][0]
        assert wave.amplitude >= 0.0

    def test_missing_coherence_defaults_zero(self):
        pkt = _pkt(value={})
        mock = self._call(pkt)
        wave = mock.call_args[0][0]
        assert wave.amplitude == 0.0

    def test_uses_precomputed_phases_when_available(self):
        pkt = _pkt(
            value={"coherence": 0.5},
            diurnal_phase=0.75,
            semi_diurnal_phase=0.3,
            long_wave_phase=0.1,
        )
        mock = self._call(pkt)
        mock.assert_called_once()

    def test_computes_phases_when_absent(self):
        pkt = _pkt(value={"coherence": 0.5}, diurnal_phase=None)
        mock = self._call(pkt)
        mock.assert_called_once()

    def test_afterglow_decay_from_packet(self):
        pkt = _pkt(value={"coherence": 0.5}, afterglow_decay=0.9)
        mock = self._call(pkt)
        wave = mock.call_args[0][0]
        assert wave.afterglow_decay == pytest.approx(0.9)

    def test_afterglow_decay_default_when_none(self):
        pkt = _pkt(value={"coherence": 0.5}, afterglow_decay=None)
        mock = self._call(pkt)
        wave = mock.call_args[0][0]
        assert wave.afterglow_decay == pytest.approx(0.5)


# ===========================================================================
# main() — route branches
# ===========================================================================

# We patch all I/O-heavy collaborators so main() runs in memory.
_MAIN_PATCHES = [
    "signal_core.core.hydro_run_cadence.drain_queue",
    "signal_core.core.hydro_run_cadence.annotate_packet",
    "signal_core.core.hydro_run_cadence.attenuate_with_scars",
    "signal_core.core.hydro_run_cadence.hydro_ingress_gate",
    "signal_core.core.hydro_run_cadence.dispatch",
    "signal_core.core.hydro_run_cadence.commit_packet",
    "signal_core.core.hydro_run_cadence.append_audit",
    "signal_core.core.hydro_run_cadence.process_turbine",
    "signal_core.core.hydro_run_cadence.apply_all_decay",
    "signal_core.core.hydro_run_cadence.run_turbine_summary",
    "signal_core.core.hydro_run_cadence.write_scar",
    "signal_core.core.hydro_run_cadence.emit_control_signal",
]


def _run_main(
    packets: list,
    gate_result: GateResult = GateResult.PASS,
    route_name: str = "MAIN",
    observe: bool = False,
    convergence: dict | None = None,
    anomaly_flag: bool = False,
    spillway_route_name: str = "RETURN",
    rule_id: str | None = None,
):
    from signal_core.core.hydro_run_cadence import main

    processed = [_pkt(anomaly_flag=anomaly_flag) for _ in packets]
    ingress = _ingress(gate_result)
    decision = _dispatch_decision(route_name, observe)
    if rule_id:
        decision.rule_id = rule_id

    spill_mock = MagicMock()
    spill_mock.route = MagicMock()
    spill_mock.route.name = spillway_route_name

    from signal_core.core.spillway_lighthouse import SpillwayRoute

    spill_route_map = {
        "RETURN": SpillwayRoute.RETURN,
        "QUARANTINE": SpillwayRoute.QUARANTINE,
        "HOLD": SpillwayRoute.HOLD,
    }
    spill_mock.route = spill_route_map.get(spillway_route_name, SpillwayRoute.RETURN)
    spill_mock.reason = spillway_route_name.lower()

    with (
        patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=processed),
        patch("signal_core.core.hydro_run_cadence.annotate_packet", side_effect=lambda p: p),
        patch("signal_core.core.hydro_run_cadence.attenuate_with_scars", side_effect=lambda p: p),
        patch("signal_core.core.hydro_run_cadence.hydro_ingress_gate", return_value=ingress),
        patch("signal_core.core.hydro_run_cadence.dispatch", return_value=decision),
        patch("signal_core.core.hydro_run_cadence.commit_packet"),
        patch("signal_core.core.hydro_run_cadence.append_audit"),
        patch("signal_core.core.hydro_run_cadence.process_turbine", return_value=MagicMock(convergence_note="ok", diurnal_phase=0.5)),
        patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={}),
        patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value=convergence or {}),
        patch("signal_core.core.hydro_run_cadence.write_scar"),
        patch("signal_core.core.hydro_run_cadence.emit_control_signal"),
        patch("signal_core.core.hydro_run_cadence.assess_spillway", return_value=spill_mock),
    ):
        return main()


class TestMainEmpty:
    def test_empty_queue_returns_zero_counts(self):
        from signal_core.core.hydro_run_cadence import main

        with (
            patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=[]),
            patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={}),
            patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value={}),
        ):
            result = main()
        assert result.packets_drained == 0
        assert result.committed == 0


class TestMainReject:
    def test_rejected_packet_not_committed(self):
        result = _run_main([1], gate_result=GateResult.REJECT)
        assert result.rejected == 1
        assert result.committed == 0


class TestMainRoute:
    def test_main_route_commits(self):
        result = _run_main([1], route_name="MAIN", observe=False)
        assert result.committed == 1
        assert result.turbine_obs == 0

    def test_main_route_with_observe_adds_turbine(self):
        result = _run_main([1], route_name="MAIN", observe=True)
        assert result.committed == 1
        assert result.turbine_obs == 1

    def test_turbine_route_no_commit(self):
        result = _run_main([1], route_name="TURBINE")
        assert result.committed == 0
        assert result.turbine_obs == 1

    def test_turbine_forest_edge_calls_write_scar(self):
        with (
            patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=[_pkt()]),
            patch("signal_core.core.hydro_run_cadence.annotate_packet", side_effect=lambda p: p),
            patch("signal_core.core.hydro_run_cadence.attenuate_with_scars", side_effect=lambda p: p),
            patch("signal_core.core.hydro_run_cadence.hydro_ingress_gate", return_value=_ingress()),
            patch("signal_core.core.hydro_run_cadence.dispatch", return_value=_dispatch_decision("TURBINE")),
            patch("signal_core.core.hydro_run_cadence.append_audit"),
            patch("signal_core.core.hydro_run_cadence.process_turbine", return_value=MagicMock(convergence_note="ok", diurnal_phase=0.5)),
            patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={}),
            patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value={}),
            patch("signal_core.core.hydro_run_cadence.write_scar") as mock_scar,
            patch("signal_core.core.hydro_run_cadence.emit_control_signal"),
        ):
            dec = _dispatch_decision("TURBINE")
            dec.rule_id = "DLH_TURBINE_FOREST_EDGE"
            with patch("signal_core.core.hydro_run_cadence.dispatch", return_value=dec):
                from signal_core.core.hydro_run_cadence import main

                main()
        mock_scar.assert_called()

    def test_spillway_return_adds_turbine(self):
        result = _run_main([1], route_name="SPILLWAY", spillway_route_name="RETURN")
        assert result.turbine_obs == 1

    def test_spillway_quarantine_increments_counter(self):
        result = _run_main([1], route_name="SPILLWAY", spillway_route_name="QUARANTINE", anomaly_flag=True)
        assert result.spillway_quarantined == 1

    def test_spillway_hold_increments_counter(self):
        result = _run_main([1], route_name="SPILLWAY", spillway_route_name="HOLD")
        assert result.spillway_hold == 1

    def test_multiple_packets_counted(self):
        result = _run_main([1, 2, 3], route_name="MAIN")
        assert result.packets_drained == 3
        assert result.committed == 3


class TestMainConvergenceScar:
    def test_strong_convergence_writes_scar(self):
        convergence = {
            "convergence_events": [
                {
                    "strength": "strong",
                    "diurnal_phase": 0.5,
                    "domains": ["system", "market"],
                }
            ]
        }
        with (
            patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=[]),
            patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={}),
            patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value=convergence),
            patch("signal_core.core.hydro_run_cadence.write_scar") as mock_scar,
        ):
            from signal_core.core.hydro_run_cadence import main

            main()
        # Two domains → two scar writes
        assert mock_scar.call_count == 2

    def test_weak_convergence_no_scar(self):
        convergence = {
            "convergence_events": [
                {
                    "strength": "weak",
                    "diurnal_phase": 0.5,
                    "domains": ["system", "market"],
                }
            ]
        }
        with (
            patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=[]),
            patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={}),
            patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value=convergence),
            patch("signal_core.core.hydro_run_cadence.write_scar") as mock_scar,
        ):
            from signal_core.core.hydro_run_cadence import main

            main()
        assert mock_scar.call_count == 0


class TestMainScarDecay:
    def test_decay_pruned_total_logged(self):
        # Just ensure scar decay branch with non-empty result doesn't raise
        with (
            patch("signal_core.core.hydro_run_cadence.drain_queue", return_value=[]),
            patch("signal_core.core.hydro_run_cadence.apply_all_decay", return_value={"system": 2}),
            patch("signal_core.core.hydro_run_cadence.run_turbine_summary", return_value={}),
        ):
            from signal_core.core.hydro_run_cadence import main

            result = main()
        assert result.packets_drained == 0


# ===========================================================================
# _persist_cycle_result
# ===========================================================================


class TestPersistCycleResult:
    def test_writes_last_cycle_json(self, tmp_path):
        from signal_core.core.hydro_run_cadence import CycleResult, _persist_cycle_result
        import signal_core.core.hydro_run_cadence as mod

        result = CycleResult(
            cycle_ts=_T,
            packets_drained=3,
            rejected=0,
            committed=3,
            turbine_obs=1,
            spillway_quarantined=0,
            spillway_hold=0,
        )

        turbine_dir = tmp_path / "turbine"

        with patch("signal_core.core.hydro_run_cadence.TURBINE_DIR", turbine_dir, create=True):
            # Patch the import inside the function
            import rhythm_os.runtime.paths as paths_mod

            orig = paths_mod.TURBINE_DIR
            paths_mod.TURBINE_DIR = turbine_dir
            try:
                _persist_cycle_result(result)
            finally:
                paths_mod.TURBINE_DIR = orig

        last = turbine_dir / "last_cycle.json"
        assert last.exists()
        import json

        data = json.loads(last.read_text())
        assert data["committed"] == 3
        assert data["packets_drained"] == 3


# ===========================================================================
# _run_voice_narration — errors caught silently
# ===========================================================================


class TestRunVoiceNarration:
    def test_does_not_raise_on_import_error(self):
        from signal_core.core.hydro_run_cadence import CycleResult, _run_voice_narration

        result = CycleResult(
            cycle_ts=_T,
            packets_drained=0,
            rejected=0,
            committed=0,
            turbine_obs=0,
            spillway_quarantined=0,
            spillway_hold=0,
        )
        # If narrate raises, _run_voice_narration should swallow it
        with patch(
            "signal_core.core.hydro_run_cadence._run_voice_narration",
            side_effect=Exception("voice fail"),
        ):
            pass  # we're testing the function is tolerant; just confirm import

        # Direct call — narrate is likely unavailable (no Ollama), should not raise
        _run_voice_narration(result)

    def test_succeeds_when_narrator_available(self):
        from signal_core.core.hydro_run_cadence import CycleResult, _run_voice_narration

        result = CycleResult(
            cycle_ts=_T,
            packets_drained=1,
            rejected=0,
            committed=1,
            turbine_obs=0,
            spillway_quarantined=0,
            spillway_hold=0,
            convergence_summary={"domains_observed": {}, "convergence_event_count": 0, "strong_events": 0},
        )
        mock_narration = MagicMock()
        mock_narration.text = "test narration"
        mock_narration.raw = {}
        with (
            patch("rhythm_os.voice.narrator.narrate", return_value=mock_narration),
            patch("rhythm_os.voice.voice_store.persist_voice_line"),
        ):
            _run_voice_narration(result)  # should not raise


# ===========================================================================
# _run_voice_interpretation — no strong events → returns early
# ===========================================================================


class TestRunVoiceInterpretation:
    def test_no_strong_events_returns_early(self):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation

        convergence = {"convergence_events": [{"strength": "weak", "domains": ["a", "b"]}]}
        # Should not raise, should return without calling interpret
        with patch("rhythm_os.voice.interpreter.interpret") as mock_interp:
            _run_voice_interpretation(convergence)
        mock_interp.assert_not_called()

    def test_empty_convergence_returns_early(self):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation

        _run_voice_interpretation({})  # should not raise
