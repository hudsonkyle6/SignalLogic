"""
Tests for rhythm_os.control_plane.turbine_action

Modules covered:
- TurbineAction dataclass (to_dict / from_dict round-trip)
- make_turbine_action factory
- append_turbine_action / load_turbine_actions persistence

Invariants:
- make_turbine_action generates a unique action_id (UUID)
- TurbineAction round-trips through to_dict / from_dict without data loss
- append_turbine_action creates the daily JSONL file and appends valid JSON
- Multiple appends accumulate in the file
- load_turbine_actions reads back what was written
- load_turbine_actions returns empty list when directory does not exist
- load_turbine_actions filters by gate_id when specified
- load_turbine_actions filters by action_type when specified
"""

from __future__ import annotations

import json

import pytest

from rhythm_os.control_plane.turbine_action import (
    ActionOutcome,
    ActionType,
    TurbineAction,
    append_turbine_action,
    load_turbine_actions,
    make_turbine_action,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _action(
    *,
    action_type: ActionType = ActionType.SIGNAL,
    gate_id: str = "gate-001",
    convergence_trigger: str = "weak:natural",
    outcome: ActionOutcome = ActionOutcome.BLOCKED,
    outcome_reason: str = "posture=OBSERVATORY_ONLY",
) -> TurbineAction:
    return make_turbine_action(
        action_type=action_type,
        gate_id=gate_id,
        convergence_trigger=convergence_trigger,
        proposed_payload={"domain": "test"},
        outcome=outcome,
        outcome_reason=outcome_reason,
    )


# ---------------------------------------------------------------------------
# TurbineAction round-trip
# ---------------------------------------------------------------------------


class TestTurbineActionRoundTrip:
    def test_to_dict_from_dict_identity(self):
        a = _action()
        d = a.to_dict()
        a2 = TurbineAction.from_dict(d)
        assert a2.action_id == a.action_id
        assert a2.action_type == a.action_type
        assert a2.gate_id == a.gate_id
        assert a2.convergence_trigger == a.convergence_trigger
        assert a2.proposed_payload == a.proposed_payload
        assert a2.outcome == a.outcome
        assert a2.outcome_reason == a.outcome_reason
        assert a2.t == pytest.approx(a.t)
        assert a2.acted_at == pytest.approx(a.acted_at)

    def test_all_action_types_round_trip(self):
        for atype in ActionType:
            a = _action(action_type=atype)
            a2 = TurbineAction.from_dict(a.to_dict())
            assert a2.action_type == atype

    def test_all_outcomes_round_trip(self):
        for outcome in ActionOutcome:
            a = _action(outcome=outcome)
            a2 = TurbineAction.from_dict(a.to_dict())
            assert a2.outcome == outcome

    def test_proposed_payload_preserved(self):
        a = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={"key": "value", "num": 42},
            outcome=ActionOutcome.BLOCKED,
            outcome_reason="test",
        )
        a2 = TurbineAction.from_dict(a.to_dict())
        assert a2.proposed_payload == {"key": "value", "num": 42}


# ---------------------------------------------------------------------------
# make_turbine_action factory
# ---------------------------------------------------------------------------


class TestMakeTurbineAction:
    def test_returns_turbine_action(self):
        a = _action()
        assert isinstance(a, TurbineAction)

    def test_unique_action_ids(self):
        ids = {_action().action_id for _ in range(10)}
        assert len(ids) == 10

    def test_action_id_is_string(self):
        a = _action()
        assert isinstance(a.action_id, str)
        assert len(a.action_id) > 0

    def test_t_is_float(self):
        a = _action()
        assert isinstance(a.t, float)

    def test_explicit_t_used(self):
        a = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
            outcome=ActionOutcome.BLOCKED,
            outcome_reason="test",
            t=12345.0,
        )
        assert a.t == pytest.approx(12345.0)

    def test_explicit_acted_at_used(self):
        a = make_turbine_action(
            action_type=ActionType.SIGNAL,
            gate_id="g1",
            convergence_trigger="x",
            proposed_payload={},
            outcome=ActionOutcome.BLOCKED,
            outcome_reason="test",
            acted_at=99999.0,
        )
        assert a.acted_at == pytest.approx(99999.0)


# ---------------------------------------------------------------------------
# append_turbine_action / load_turbine_actions
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_append_creates_file(self, tmp_path):
        a = _action()
        append_turbine_action(a, store_dir=tmp_path)
        files = list(tmp_path.glob("actions-*.jsonl"))
        assert len(files) == 1

    def test_appended_line_is_valid_json(self, tmp_path):
        a = _action()
        append_turbine_action(a, store_dir=tmp_path)
        path = next(tmp_path.glob("actions-*.jsonl"))
        parsed = json.loads(path.read_text().strip())
        assert isinstance(parsed, dict)
        assert parsed["action_id"] == a.action_id

    def test_multiple_appends_accumulate(self, tmp_path):
        for _ in range(3):
            append_turbine_action(_action(), store_dir=tmp_path)
        path = next(tmp_path.glob("actions-*.jsonl"))
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_load_empty_directory_returns_empty(self, tmp_path):
        result = load_turbine_actions(store_dir=tmp_path / "nonexistent")
        assert result == []

    def test_load_reads_back_action(self, tmp_path):
        a = _action()
        append_turbine_action(a, store_dir=tmp_path)
        results = load_turbine_actions(store_dir=tmp_path)
        assert len(results) == 1
        assert results[0].action_id == a.action_id

    def test_load_filter_by_gate_id(self, tmp_path):
        a1 = _action(gate_id="g1")
        a2 = _action(gate_id="g2")
        append_turbine_action(a1, store_dir=tmp_path)
        append_turbine_action(a2, store_dir=tmp_path)
        results = load_turbine_actions(store_dir=tmp_path, gate_id="g1")
        assert all(r.gate_id == "g1" for r in results)
        assert len(results) == 1

    def test_load_filter_by_action_type(self, tmp_path):
        a1 = _action(action_type=ActionType.SIGNAL)
        a2 = _action(action_type=ActionType.ROUTE_ADJUST)
        append_turbine_action(a1, store_dir=tmp_path)
        append_turbine_action(a2, store_dir=tmp_path)
        results = load_turbine_actions(
            store_dir=tmp_path, action_type=ActionType.SIGNAL
        )
        assert all(r.action_type == ActionType.SIGNAL for r in results)
        assert len(results) == 1

    def test_load_respects_max_records(self, tmp_path):
        for _ in range(10):
            append_turbine_action(_action(), store_dir=tmp_path)
        results = load_turbine_actions(store_dir=tmp_path, max_records=3)
        assert len(results) == 3
