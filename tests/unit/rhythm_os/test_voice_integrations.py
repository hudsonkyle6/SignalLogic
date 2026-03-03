"""
Tests for the three voice integration points:

1. _run_voice_narration  (hydro_run_cadence)
2. _run_voice_interpretation  (hydro_run_cadence)
3. GateAuthority.resolve_action counselor advisory  (gate_authority)
4. TurbineAction counselor fields  (turbine_action)

Invariants:
- _run_voice_narration persists a VoiceLine(mode="narrator") for a normal cycle
- _run_voice_narration is a no-op when narrate() raises (never re-raises)
- _run_voice_narration builds cycle_summary from CycleResult fields
- _run_voice_narration text is truncated to <=2 sentences

- _run_voice_interpretation is a no-op when there are no strong events
- _run_voice_interpretation records each domain pair in ConvergenceMemoryStore
- _run_voice_interpretation persists a VoiceLine(mode="interpreter") per strong pair
- _run_voice_interpretation is a no-op when interpret() raises (never re-raises)

- resolve_action includes counselor_verdict in returned TurbineAction
- resolve_action includes counselor_justification in returned TurbineAction
- resolve_action passes action_type, gate_id, convergence_trigger to counselor
- resolve_action does not raise when counsel_fn raises (advisory only)
- counselor_verdict is None when no counsel_fn and Ollama unavailable
- counselor verdict DOES NOT override authority hard decision

- TurbineAction.to_dict includes counselor_verdict + counselor_justification
- TurbineAction.from_dict reads counselor fields when present
- TurbineAction.from_dict defaults counselor fields to None when absent (backward compat)
- make_turbine_action accepts counselor_verdict + counselor_justification
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from rhythm_os.control_plane.gate_authority import GateAuthority
from rhythm_os.control_plane.gate_store import ActionScope, GateState
from rhythm_os.control_plane.turbine_action import (
    ActionOutcome,
    ActionType,
    TurbineAction,
    make_turbine_action,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_open_gate_store(gate_id: str, scope: ActionScope):
    """Return a GateStore stub with one open gate."""
    from rhythm_os.control_plane.gate_store import Gate

    gate = Gate(
        gate_id=gate_id,
        scope=scope,
        state=GateState.OPEN,
        opened_at=1.0,
        opened_by="test",
        mandate_id="m-001",
        closed_at=None,
        closed_reason=None,
    )
    store = MagicMock()
    store.get_gate.return_value = gate
    return store


def _counsel_proceed(ctx: Dict[str, Any]):
    """Stub counselor that always returns PROCEED."""
    from rhythm_os.voice.gate_counselor import CounselorResult

    return CounselorResult(
        recommendation="PROCEED",
        justification="Evidence is strong.",
        raw="PROCEED Evidence is strong.",
    )


def _counsel_defer(ctx: Dict[str, Any]):
    """Stub counselor that always returns DEFER."""
    from rhythm_os.voice.gate_counselor import CounselorResult

    return CounselorResult(
        recommendation="DEFER",
        justification="Insufficient evidence.",
        raw="DEFER Insufficient evidence.",
    )


def _make_cycle_result(convergence_summary=None):
    """Build a minimal CycleResult for narrator tests."""
    from signal_core.core.hydro_run_cadence import CycleResult

    return CycleResult(
        cycle_ts=1000.0,
        packets_drained=100,
        rejected=5,
        committed=80,
        turbine_obs=15,
        spillway_quarantined=0,
        spillway_hold=0,
        convergence_summary=convergence_summary,
    )


# ---------------------------------------------------------------------------
# TurbineAction counselor fields
# ---------------------------------------------------------------------------


class TestTurbineActionCounselorFields:
    def test_make_turbine_action_defaults_counselor_to_none(self):
        action = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="convergence:natural,system",
            proposed_payload={},
            outcome=ActionOutcome.EXECUTED,
            outcome_reason="ok",
        )
        assert action.counselor_verdict is None
        assert action.counselor_justification is None

    def test_make_turbine_action_accepts_counselor_fields(self):
        action = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="convergence:natural,system",
            proposed_payload={},
            outcome=ActionOutcome.EXECUTED,
            outcome_reason="ok",
            counselor_verdict="PROCEED",
            counselor_justification="Evidence is strong.",
        )
        assert action.counselor_verdict == "PROCEED"
        assert action.counselor_justification == "Evidence is strong."

    def test_to_dict_includes_counselor_fields(self):
        action = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="c:x",
            proposed_payload={},
            outcome=ActionOutcome.EXECUTED,
            outcome_reason="ok",
            counselor_verdict="DEFER",
            counselor_justification="Risk too high.",
        )
        d = action.to_dict()
        assert d["counselor_verdict"] == "DEFER"
        assert d["counselor_justification"] == "Risk too high."

    def test_to_dict_counselor_none_when_not_set(self):
        action = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="c:x",
            proposed_payload={},
            outcome=ActionOutcome.EXECUTED,
            outcome_reason="ok",
        )
        d = action.to_dict()
        assert d["counselor_verdict"] is None
        assert d["counselor_justification"] is None

    def test_from_dict_reads_counselor_fields(self):
        action = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="c:x",
            proposed_payload={},
            outcome=ActionOutcome.EXECUTED,
            outcome_reason="ok",
            counselor_verdict="PROCEED",
            counselor_justification="Strong signal.",
        )
        restored = TurbineAction.from_dict(action.to_dict())
        assert restored.counselor_verdict == "PROCEED"
        assert restored.counselor_justification == "Strong signal."

    def test_from_dict_backward_compat_missing_counselor(self):
        """Old JSONL records without counselor fields should deserialize cleanly."""
        d = {
            "action_id": "abc",
            "t": 1.0,
            "action_type": "SIGNAL",
            "gate_id": "g-001",
            "convergence_trigger": "c:x",
            "proposed_payload": {},
            "outcome": "EXECUTED",
            "outcome_reason": "ok",
            "acted_at": 1.0,
            # counselor_verdict and counselor_justification absent
        }
        action = TurbineAction.from_dict(d)
        assert action.counselor_verdict is None
        assert action.counselor_justification is None


# ---------------------------------------------------------------------------
# GateAuthority counselor advisory
# ---------------------------------------------------------------------------


class TestGateAuthorityCounselorAdvisory:
    @pytest.fixture(autouse=True)
    def _isolate_voice_store(self, monkeypatch, tmp_path):
        """Redirect VOICE_LINES_PATH so counselor tests never write to real data."""
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", tmp_path / "voice_lines.jsonl")

    def _authority(self, gate_id="g-001", scope=ActionScope.SIGNAL, tmp_path=None):
        store = _make_open_gate_store(gate_id, scope)
        return GateAuthority(store, persist_actions=False, store_dir=tmp_path)

    def test_counselor_verdict_in_action_on_proceed(self, monkeypatch, tmp_path):
        auth = self._authority(tmp_path=tmp_path)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="convergence:natural,system",
            proposed_payload={"domain_pair": "natural+system"},
            counsel_fn=_counsel_proceed,
        )
        assert action.counselor_verdict == "PROCEED"
        assert action.counselor_justification == "Evidence is strong."

    def test_counselor_defer_does_not_override_authority_proceed(
        self, monkeypatch, tmp_path
    ):
        """Counselor saying DEFER must not block a PROCEED from the authority."""
        auth = self._authority(tmp_path=tmp_path)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="convergence:natural,system",
            proposed_payload={},
            counsel_fn=_counsel_defer,
        )
        # Counselor said DEFER but authority says PROCEED → action still EXECUTED
        assert action.outcome == ActionOutcome.EXECUTED
        assert action.counselor_verdict == "DEFER"

    def test_counselor_verdict_on_blocked_action(self, monkeypatch, tmp_path):
        """Counselor advisory is recorded even when authority blocks."""
        store = MagicMock()
        store.get_gate.return_value = None  # gate not found → BLOCK
        auth = GateAuthority(store, persist_actions=False)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-999",
            convergence_trigger="c:x",
            proposed_payload={},
            counsel_fn=_counsel_proceed,
        )
        assert action.outcome == ActionOutcome.BLOCKED
        assert action.counselor_verdict == "PROCEED"  # counselor ran, authority blocked

    def test_counselor_error_does_not_raise(self, monkeypatch, tmp_path):
        """A raising counsel_fn must not propagate — advisory only."""
        auth = self._authority(tmp_path=tmp_path)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        def _broken(ctx):
            raise RuntimeError("ollama down")

        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="c:x",
            proposed_payload={},
            counsel_fn=_broken,
        )
        # Action still completes; counselor fields are None
        assert action.counselor_verdict is None
        assert action.counselor_justification is None
        assert action.outcome == ActionOutcome.EXECUTED

    def test_counsel_fn_receives_action_context_keys(self, monkeypatch, tmp_path):
        auth = self._authority(tmp_path=tmp_path)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        captured = []

        def _capturing(ctx):
            captured.append(ctx)
            return _counsel_proceed(ctx)

        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="convergence:natural,system",
            proposed_payload={"domain_pair": "natural+system"},
            counsel_fn=_capturing,
        )
        assert len(captured) == 1
        ctx = captured[0]
        assert ctx["action_type"] == "SIGNAL"
        assert ctx["gate_id"] == "g-001"
        assert ctx["convergence_trigger"] == "convergence:natural,system"
        assert ctx["domain_pair"] == "natural+system"

    def test_counselor_verdict_persisted_as_voice_line(self, monkeypatch, tmp_path):
        """Counselor result should be saved to voice_store."""
        from rhythm_os.voice.voice_store import load_last_voice_line

        store_path = tmp_path / "voice_lines.jsonl"
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", store_path)

        auth = self._authority(tmp_path=tmp_path)
        monkeypatch.setattr("rhythm_os.core.posture.SYSTEM_POSTURE", "ACTIVE")
        import rhythm_os.control_plane.gate_authority as mod

        monkeypatch.setattr(mod, "SYSTEM_POSTURE", "ACTIVE")

        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g-001",
            convergence_trigger="c:x",
            proposed_payload={},
            counsel_fn=_counsel_proceed,
        )
        vl = load_last_voice_line(mode="counselor", store_path=store_path)
        assert vl is not None
        assert "PROCEED" in vl.text


# ---------------------------------------------------------------------------
# _run_voice_narration
# ---------------------------------------------------------------------------


class TestRunVoiceNarration:
    def test_persists_narrator_voice_line(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_narration
        from rhythm_os.voice.voice_store import load_last_voice_line

        store_path = tmp_path / "vl.jsonl"
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", store_path)

        result = _make_cycle_result(
            convergence_summary={
                "domains_observed": {"natural": 5, "system": 3},
                "convergence_event_count": 1,
                "strong_events": 1,
                "convergence_events": [],
            }
        )

        def _gen(prompt):
            return "The cycle completed with activity. Twelve packets were admitted."

        from rhythm_os.voice import narrator as nar_mod

        monkeypatch.setattr(
            nar_mod,
            "narrate",
            lambda cs, **kw: nar_mod.NarratorResult(
                text="The cycle completed with activity.",
                raw="The cycle completed with activity. Twelve packets were admitted.",
            ),
        )

        _run_voice_narration(result)

        vl = load_last_voice_line(mode="narrator", store_path=store_path)
        assert vl is not None
        assert vl.mode == "narrator"

    def test_does_not_raise_when_narrate_raises(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_narration

        result = _make_cycle_result()

        import rhythm_os.voice.narrator as nar_mod

        monkeypatch.setattr(
            nar_mod,
            "narrate",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("ollama down")),
        )

        # Must not raise
        _run_voice_narration(result)

    def test_cycle_summary_includes_committed_count(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_narration

        result = _make_cycle_result()
        captured = []

        import rhythm_os.voice.narrator as nar_mod

        def _capturing_narrate(cs, **kw):
            captured.append(cs)
            return nar_mod.NarratorResult(text="A.", raw="A.")

        monkeypatch.setattr(nar_mod, "narrate", _capturing_narrate)
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", tmp_path / "vl.jsonl")

        _run_voice_narration(result)

        assert len(captured) == 1
        assert captured[0]["packets_admitted"] == result.committed
        assert captured[0]["packets_drained"] == result.packets_drained

    def test_domains_seen_extracted_from_convergence_summary(
        self, monkeypatch, tmp_path
    ):
        from signal_core.core.hydro_run_cadence import _run_voice_narration

        result = _make_cycle_result(
            convergence_summary={
                "domains_observed": {"natural": 10, "system": 5, "market": 2}
            }
        )
        captured = []

        import rhythm_os.voice.narrator as nar_mod

        def _capturing_narrate(cs, **kw):
            captured.append(cs)
            return nar_mod.NarratorResult(text="A.", raw="A.")

        monkeypatch.setattr(nar_mod, "narrate", _capturing_narrate)
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", tmp_path / "vl.jsonl")

        _run_voice_narration(result)

        assert set(captured[0]["domains_seen"]) == {"natural", "system", "market"}


# ---------------------------------------------------------------------------
# _run_voice_interpretation
# ---------------------------------------------------------------------------


class TestRunVoiceInterpretation:
    def _strong_convergence(self, domains=None, phase=0.064):
        if domains is None:
            domains = ["market", "natural", "system"]
        return {
            "convergence_events": [
                {
                    "domains": sorted(domains),
                    "diurnal_phase": phase,
                    "strength": "strong",
                }
            ],
            "convergence_event_count": 1,
            "strong_events": 1,
        }

    def test_no_op_when_no_strong_events(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation

        store_path = tmp_path / "vl.jsonl"
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", store_path)

        convergence = {
            "convergence_events": [
                {
                    "domains": ["natural", "system"],
                    "diurnal_phase": 0.1,
                    "strength": "weak",
                }
            ],
            "strong_events": 0,
        }
        _run_voice_interpretation(convergence)
        assert not store_path.exists()

    def test_no_op_when_no_convergence_events(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation

        store_path = tmp_path / "vl.jsonl"
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", store_path)

        _run_voice_interpretation({})
        assert not store_path.exists()

    def test_persists_interpreter_voice_line_for_strong_event(
        self, monkeypatch, tmp_path
    ):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation
        from rhythm_os.voice.voice_store import load_last_voice_line
        from rhythm_os.voice.interpreter import InterpretationResult

        store_path = tmp_path / "vl.jsonl"
        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", store_path)

        import rhythm_os.voice.interpreter as interp_mod

        monkeypatch.setattr(
            interp_mod,
            "interpret",
            lambda hs, **kw: InterpretationResult(
                convergence_type="NOISE",
                rationale="Daily shared rhythm.",
                raw="NOISE Daily shared rhythm.",
            ),
        )
        # Also patch ConvergenceMemoryStore to avoid disk writes
        import rhythm_os.domain.convergence.memory_store as ms_mod

        fake_store = MagicMock()
        fake_store.pair_summary.return_value = {"total_count": 1}
        monkeypatch.setattr(
            ms_mod, "ConvergenceMemoryStore", lambda *a, **kw: fake_store
        )

        _run_voice_interpretation(self._strong_convergence())

        vl = load_last_voice_line(mode="interpreter", store_path=store_path)
        assert vl is not None
        assert vl.mode == "interpreter"
        assert "NOISE" in vl.text

    def test_records_each_domain_pair(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation
        from rhythm_os.voice.interpreter import InterpretationResult

        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", tmp_path / "vl.jsonl")

        import rhythm_os.voice.interpreter as interp_mod

        monkeypatch.setattr(
            interp_mod,
            "interpret",
            lambda hs, **kw: InterpretationResult(
                convergence_type="COUPLING", rationale="R.", raw="COUPLING R."
            ),
        )

        recorded_pairs = []
        import rhythm_os.domain.convergence.memory_store as ms_mod

        fake_store = MagicMock()
        fake_store.record.side_effect = lambda **kw: recorded_pairs.append(
            (kw["domain_a"], kw["domain_b"])
        )
        fake_store.pair_summary.return_value = {"total_count": 1}
        monkeypatch.setattr(
            ms_mod, "ConvergenceMemoryStore", lambda *a, **kw: fake_store
        )

        # 3 domains → 3 pairs: (m,n), (m,s), (n,s)
        _run_voice_interpretation(
            self._strong_convergence(["market", "natural", "system"])
        )

        assert len(recorded_pairs) == 3
        assert ("market", "natural") in recorded_pairs
        assert ("market", "system") in recorded_pairs
        assert ("natural", "system") in recorded_pairs

    def test_does_not_raise_when_interpret_raises(self, monkeypatch, tmp_path):
        from signal_core.core.hydro_run_cadence import _run_voice_interpretation

        import rhythm_os.voice.voice_store as vs_mod

        monkeypatch.setattr(vs_mod, "VOICE_LINES_PATH", tmp_path / "vl.jsonl")

        import rhythm_os.voice.interpreter as interp_mod

        monkeypatch.setattr(
            interp_mod,
            "interpret",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("ollama down")),
        )

        import rhythm_os.domain.convergence.memory_store as ms_mod

        fake_store = MagicMock()
        fake_store.pair_summary.return_value = {}
        monkeypatch.setattr(
            ms_mod, "ConvergenceMemoryStore", lambda *a, **kw: fake_store
        )

        # Must not raise
        _run_voice_interpretation(self._strong_convergence())
