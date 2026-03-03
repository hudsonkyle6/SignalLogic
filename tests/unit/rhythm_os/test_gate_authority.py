"""
Tests for rhythm_os.control_plane.gate_authority

Modules covered:
- AuthorityDecision enum
- AuthorityResult dataclass
- GateAuthority.evaluate
- GateAuthority.resolve_action

Invariants:
- evaluate always returns BLOCK when posture is OBSERVATORY_ONLY
- evaluate returns BLOCK when gate does not exist
- evaluate returns BLOCK when gate is CLOSED
- evaluate returns BLOCK on scope mismatch
- evaluate returns BLOCK when mandate is stale
- evaluate returns PROCEED when gate is open, scope matches, mandate fresh
- resolve_action returns BLOCKED TurbineAction when authority blocks
- resolve_action returns EXECUTED TurbineAction when authority proceeds
- resolve_action returns FAILED when executor raises
- resolve_action logs action when persist=True
- resolve_action does not log when persist=False

Note: SYSTEM_POSTURE is OBSERVATORY_ONLY in this codebase.
All non-posture paths are tested by monkeypatching the posture.
"""

from __future__ import annotations

import time
from pathlib import Path


from rhythm_os.control_plane.gate_authority import (
    AuthorityDecision,
    GateAuthority,
)
from rhythm_os.control_plane.gate_store import ActionScope, GateStore
from rhythm_os.control_plane.turbine_action import ActionOutcome, ActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> GateStore:
    return GateStore(store_path=tmp_path / "gates.jsonl")


def _authority(
    store: GateStore, tmp_path: Path, persist: bool = False
) -> GateAuthority:
    return GateAuthority(
        gate_store=store, persist_actions=persist, store_dir=tmp_path / "actions"
    )


def _open_gate(
    store: GateStore,
    gate_id: str = "g1",
    scope: ActionScope = ActionScope.SIGNAL,
) -> None:
    store.open_gate(gate_id, scope, opened_by="operator", mandate_id="m1")


def _fresh_mandate():
    """Return a fresh Mandate (valid for 1 hour)."""
    from rhythm_os.control_plane.mandate import Mandate

    now = int(time.time())
    return Mandate(
        principal="test-operator",
        issued_at=now - 60,
        expires_at=now + 3600,
        scope="gate:SIGNAL",
        nonce="test-nonce",
        signature="test-sig",
    )


def _stale_mandate():
    """Return a mandate that is already expired."""
    from rhythm_os.control_plane.mandate import Mandate

    now = int(time.time())
    return Mandate(
        principal="test-operator",
        issued_at=now - 7200,
        expires_at=now - 3600,
        scope="gate:SIGNAL",
        nonce="test-nonce",
        signature="test-sig",
    )


def _patch_posture(monkeypatch, posture: str) -> None:
    """Monkeypatch SYSTEM_POSTURE in gate_authority module."""
    import rhythm_os.control_plane.gate_authority as mod

    monkeypatch.setattr(mod, "SYSTEM_POSTURE", posture)


# ---------------------------------------------------------------------------
# evaluate — posture check
# ---------------------------------------------------------------------------


class TestEvaluatePosture:
    def test_observatory_only_always_blocks(self, tmp_path):
        store = _store(tmp_path)
        _open_gate(store)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1")
        assert result.decision == AuthorityDecision.BLOCK
        assert "OBSERVATORY_ONLY" in result.reason

    def test_observatory_only_blocks_even_with_open_gate(self, tmp_path):
        store = _store(tmp_path)
        _open_gate(store)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1", mandate=_fresh_mandate())
        assert result.decision == AuthorityDecision.BLOCK


# ---------------------------------------------------------------------------
# evaluate — gate checks (posture bypassed via monkeypatch)
# ---------------------------------------------------------------------------


class TestEvaluateGateChecks:
    def test_gate_not_found_blocks(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "nonexistent")
        assert result.decision == AuthorityDecision.BLOCK
        assert "gate_not_found" in result.reason

    def test_closed_gate_blocks(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store)
        store.close_gate("g1")
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1")
        assert result.decision == AuthorityDecision.BLOCK
        assert "gate_closed" in result.reason

    def test_scope_mismatch_blocks(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.ROUTE_ADJUST)  # ROUTE_ADJUST gate
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1")  # SIGNAL action
        assert result.decision == AuthorityDecision.BLOCK
        assert "scope_mismatch" in result.reason

    def test_stale_mandate_blocks(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1", mandate=_stale_mandate())
        assert result.decision == AuthorityDecision.BLOCK
        assert "stale_or_expired_mandate" in result.reason

    def test_open_gate_matching_scope_proceeds(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1")
        assert result.decision == AuthorityDecision.PROCEED

    def test_open_gate_with_fresh_mandate_proceeds(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1", mandate=_fresh_mandate())
        assert result.decision == AuthorityDecision.PROCEED

    def test_gate_returned_in_result_when_found(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1")
        assert result.gate is not None
        assert result.gate.gate_id == "g1"

    def test_no_mandate_proceeds_when_gate_open(self, monkeypatch, tmp_path):
        """Mandate is optional — absence doesn't block if gate is open."""
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        result = auth.evaluate(ActionType.SIGNAL, "g1", mandate=None)
        assert result.decision == AuthorityDecision.PROCEED

    def test_all_scope_action_type_pairs(self, monkeypatch, tmp_path):
        """Each ActionType proceeds when the matching scope gate is open."""
        _patch_posture(monkeypatch, "ACTIVE")
        pairs = [
            (ActionType.SIGNAL, ActionScope.SIGNAL),
            (ActionType.ROUTE_ADJUST, ActionScope.ROUTE_ADJUST),
            (ActionType.EXTERNAL, ActionScope.EXTERNAL),
            (ActionType.GATE_CONTROL, ActionScope.GATE_CONTROL),
        ]
        for i, (atype, scope) in enumerate(pairs):
            store = GateStore(store_path=tmp_path / f"gates_{i}.jsonl")
            store.open_gate(f"g{i}", scope, "op", "m1")
            auth = GateAuthority(gate_store=store, persist_actions=False)
            result = auth.evaluate(atype, f"g{i}")
            assert result.decision == AuthorityDecision.PROCEED, f"Failed for {atype}"


# ---------------------------------------------------------------------------
# resolve_action
# ---------------------------------------------------------------------------


class TestResolveAction:
    def test_blocked_by_posture_returns_blocked_action(self, tmp_path):
        store = _store(tmp_path)
        _open_gate(store)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="test",
            proposed_payload={"x": 1},
        )
        assert action.outcome == ActionOutcome.BLOCKED
        assert "OBSERVATORY_ONLY" in action.outcome_reason

    def test_blocked_gate_not_found_returns_blocked(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="no-gate",
            convergence_trigger="test",
            proposed_payload={},
        )
        assert action.outcome == ActionOutcome.BLOCKED

    def test_proceeds_when_gate_open(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="convergence:natural,system",
            proposed_payload={"signal": "forward"},
        )
        assert action.outcome == ActionOutcome.EXECUTED

    def test_executor_called_on_proceed(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)
        called_with = []
        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
            executor=lambda a: called_with.append(a),
        )
        assert len(called_with) == 1

    def test_executor_not_called_on_block(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        auth = _authority(store, tmp_path)
        called = []
        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="no-gate",
            convergence_trigger="x",
            proposed_payload={},
            executor=lambda a: called.append(a),
        )
        assert called == []

    def test_executor_error_produces_failed_outcome(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        auth = _authority(store, tmp_path)

        def _bad_executor(_):
            raise RuntimeError("something went wrong")

        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
            executor=_bad_executor,
        )
        assert action.outcome == ActionOutcome.FAILED
        assert "executor_error" in action.outcome_reason

    def test_persist_true_writes_action_log(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        actions_dir = tmp_path / "actions"
        auth = GateAuthority(
            gate_store=store, persist_actions=True, store_dir=actions_dir
        )
        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
        )
        assert actions_dir.exists()
        files = list(actions_dir.glob("actions-*.jsonl"))
        assert len(files) == 1

    def test_persist_false_no_action_log(self, monkeypatch, tmp_path):
        _patch_posture(monkeypatch, "ACTIVE")
        store = _store(tmp_path)
        _open_gate(store, scope=ActionScope.SIGNAL)
        actions_dir = tmp_path / "actions"
        auth = GateAuthority(
            gate_store=store, persist_actions=False, store_dir=actions_dir
        )
        auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
        )
        assert not actions_dir.exists()

    def test_returns_turbine_action_instance(self, tmp_path):
        from rhythm_os.control_plane.turbine_action import TurbineAction

        store = _store(tmp_path)
        _open_gate(store)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
        )
        assert isinstance(action, TurbineAction)

    def test_gate_id_recorded_in_action(self, tmp_path):
        store = _store(tmp_path)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="my-specific-gate",
            convergence_trigger="x",
            proposed_payload={},
        )
        assert action.gate_id == "my-specific-gate"

    def test_convergence_trigger_recorded(self, tmp_path):
        store = _store(tmp_path)
        auth = _authority(store, tmp_path)
        action = auth.resolve_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="convergence:natural,system",
            proposed_payload={},
        )
        assert action.convergence_trigger == "convergence:natural,system"
