"""
Tests for rhythm_os.control_plane.gate_store

Modules covered:
- Gate dataclass (to_dict / from_dict round-trip)
- GateStore.open_gate
- GateStore.close_gate (kill-switch invariant)
- GateStore.get_gate
- GateStore.is_open
- GateStore.list_open_gates
- GateStore.list_all_gates

Invariants:
- open_gate raises GateStoreError on empty gate_id / opened_by / mandate_id
- open_gate raises GateStoreError if gate is already OPEN
- close_gate is always instantaneous — no conditions, no errors
- close_gate on a non-existent gate still logs a closed record (no-op safe)
- close_gate on an already-closed gate does not raise
- is_open returns False for unknown / closed gates, True for open ones
- list_open_gates returns only OPEN gates sorted by opened_at
- Gate round-trips through to_dict / from_dict without data loss
"""

from __future__ import annotations

import time

import pytest

from rhythm_os.control_plane.gate_store import (
    ActionScope,
    Gate,
    GateState,
    GateStore,
    GateStoreError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path) -> GateStore:
    return GateStore(store_path=tmp_path / "gates.jsonl")


def _open(
    store: GateStore, gate_id: str = "g1", scope: ActionScope = ActionScope.SIGNAL
) -> Gate:
    return store.open_gate(
        gate_id=gate_id,
        scope=scope,
        opened_by="operator",
        mandate_id="mandate-abc",
    )


# ---------------------------------------------------------------------------
# Gate round-trip
# ---------------------------------------------------------------------------


class TestGateRoundTrip:
    def test_open_gate_round_trip(self, tmp_path):
        g = _open(_store(tmp_path))
        d = g.to_dict()
        g2 = Gate.from_dict(d)
        assert g2.gate_id == g.gate_id
        assert g2.scope == g.scope
        assert g2.state == g.state
        assert g2.opened_by == g.opened_by
        assert g2.mandate_id == g.mandate_id
        assert g2.closed_at is None
        assert g2.closed_reason is None

    def test_closed_gate_round_trip(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        closed = store.close_gate("g1", reason="test_close")
        d = closed.to_dict()
        g2 = Gate.from_dict(d)
        assert g2.state == GateState.CLOSED
        assert g2.closed_reason == "test_close"
        assert g2.closed_at is not None


# ---------------------------------------------------------------------------
# open_gate
# ---------------------------------------------------------------------------


class TestOpenGate:
    def test_returns_gate_with_open_state(self, tmp_path):
        g = _open(_store(tmp_path))
        assert g.state == GateState.OPEN

    def test_gate_id_stored_correctly(self, tmp_path):
        g = _open(_store(tmp_path), gate_id="my-gate")
        assert g.gate_id == "my-gate"

    def test_scope_stored_correctly(self, tmp_path):
        g = _open(_store(tmp_path), scope=ActionScope.ROUTE_ADJUST)
        assert g.scope == ActionScope.ROUTE_ADJUST

    def test_opened_by_stored(self, tmp_path):
        store = _store(tmp_path)
        g = store.open_gate("g1", ActionScope.SIGNAL, "alice", "m1")
        assert g.opened_by == "alice"

    def test_mandate_id_stored(self, tmp_path):
        store = _store(tmp_path)
        g = store.open_gate("g1", ActionScope.SIGNAL, "alice", "m1")
        assert g.mandate_id == "m1"

    def test_raises_on_empty_gate_id(self, tmp_path):
        store = _store(tmp_path)
        with pytest.raises(GateStoreError):
            store.open_gate("", ActionScope.SIGNAL, "alice", "m1")

    def test_raises_on_empty_opened_by(self, tmp_path):
        store = _store(tmp_path)
        with pytest.raises(GateStoreError):
            store.open_gate("g1", ActionScope.SIGNAL, "", "m1")

    def test_raises_on_empty_mandate_id(self, tmp_path):
        store = _store(tmp_path)
        with pytest.raises(GateStoreError):
            store.open_gate("g1", ActionScope.SIGNAL, "alice", "")

    def test_raises_if_already_open(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        with pytest.raises(GateStoreError):
            _open(store)

    def test_can_reopen_after_close(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        g = _open(store)
        assert g.state == GateState.OPEN

    def test_persists_to_file(self, tmp_path):
        path = tmp_path / "gates.jsonl"
        store = GateStore(store_path=path)
        _open(store)
        assert path.exists()
        content = path.read_text(encoding="utf-8").strip()
        assert len(content.splitlines()) == 1


# ---------------------------------------------------------------------------
# close_gate (kill-switch invariant)
# ---------------------------------------------------------------------------


class TestCloseGate:
    def test_close_returns_closed_state(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        closed = store.close_gate("g1")
        assert closed.state == GateState.CLOSED

    def test_close_sets_closed_at(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        before = time.time()
        closed = store.close_gate("g1")
        after = time.time()
        assert closed.closed_at is not None
        assert before <= closed.closed_at <= after

    def test_close_stores_reason(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        closed = store.close_gate("g1", reason="kill_switch_test")
        assert closed.closed_reason == "kill_switch_test"

    def test_kill_switch_on_nonexistent_gate_does_not_raise(self, tmp_path):
        # Closing a gate that was never opened must NEVER raise
        store = _store(tmp_path)
        result = store.close_gate("never-existed")
        assert result.state == GateState.CLOSED

    def test_kill_switch_on_already_closed_gate_does_not_raise(self, tmp_path):
        # Double-close must NEVER raise
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        result = store.close_gate("g1", reason="second_close")
        assert result.state == GateState.CLOSED

    def test_close_is_persisted(self, tmp_path):
        path = tmp_path / "gates.jsonl"
        store = GateStore(store_path=path)
        _open(store)
        store.close_gate("g1")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2  # one open + one close record

    def test_after_close_is_open_returns_false(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        assert store.is_open("g1") is False


# ---------------------------------------------------------------------------
# get_gate / is_open
# ---------------------------------------------------------------------------


class TestGetGateAndIsOpen:
    def test_unknown_gate_returns_none(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_gate("nonexistent") is None

    def test_is_open_false_for_unknown(self, tmp_path):
        store = _store(tmp_path)
        assert store.is_open("nonexistent") is False

    def test_get_gate_returns_current_state(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        g = store.get_gate("g1")
        assert g is not None
        assert g.state == GateState.OPEN

    def test_is_open_true_after_open(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        assert store.is_open("g1") is True

    def test_get_gate_reflects_close(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        g = store.get_gate("g1")
        assert g is not None
        assert g.state == GateState.CLOSED


# ---------------------------------------------------------------------------
# list_open_gates / list_all_gates
# ---------------------------------------------------------------------------


class TestListGates:
    def test_list_open_empty_store(self, tmp_path):
        store = _store(tmp_path)
        assert store.list_open_gates() == []

    def test_list_all_empty_store(self, tmp_path):
        store = _store(tmp_path)
        assert store.list_all_gates() == []

    def test_open_gate_appears_in_list_open(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        open_gates = store.list_open_gates()
        assert len(open_gates) == 1
        assert open_gates[0].gate_id == "g1"

    def test_closed_gate_not_in_list_open(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        assert store.list_open_gates() == []

    def test_closed_gate_appears_in_list_all(self, tmp_path):
        store = _store(tmp_path)
        _open(store)
        store.close_gate("g1")
        all_gates = store.list_all_gates()
        assert len(all_gates) == 1
        assert all_gates[0].state == GateState.CLOSED

    def test_multiple_open_gates_sorted_by_opened_at(self, tmp_path):
        path = tmp_path / "gates.jsonl"
        store = GateStore(store_path=path)
        t1 = 1000.0
        t2 = 2000.0
        store.open_gate("g-late", ActionScope.SIGNAL, "op", "m1", now=t2)
        store.open_gate("g-early", ActionScope.SIGNAL, "op", "m2", now=t1)
        open_gates = store.list_open_gates()
        assert [g.gate_id for g in open_gates] == ["g-early", "g-late"]

    def test_mixed_gates_list_open_only_shows_open(self, tmp_path):
        path = tmp_path / "gates.jsonl"
        store = GateStore(store_path=path)
        store.open_gate("g-open", ActionScope.SIGNAL, "op", "m1")
        store.open_gate("g-closed", ActionScope.ROUTE_ADJUST, "op", "m2")
        store.close_gate("g-closed")
        open_gates = store.list_open_gates()
        assert len(open_gates) == 1
        assert open_gates[0].gate_id == "g-open"

    def test_all_scopes_supported(self, tmp_path):
        path = tmp_path / "gates.jsonl"
        store = GateStore(store_path=path)
        for i, scope in enumerate(ActionScope):
            store.open_gate(f"g{i}", scope, "op", f"m{i}")
        open_gates = store.list_open_gates()
        scopes = {g.scope for g in open_gates}
        assert scopes == set(ActionScope)
