"""
Tests for:
  - rhythm_os.runtime.cycle_id.compute_cycle_id
  - rhythm_os.runtime.field_cycle (is_valid_field_cycle, find_invalid_field_cycles)
"""

from __future__ import annotations

import pytest

from rhythm_os.runtime.cycle_id import compute_cycle_id
from rhythm_os.runtime.field_cycle import (
    CANONICAL_FIELD_CYCLES,
    find_invalid_field_cycles,
    is_valid_field_cycle,
)


# ---------------------------------------------------------------------------
# compute_cycle_id
# ---------------------------------------------------------------------------


class TestComputeCycleId:
    def test_returns_64_hex_chars(self):
        cid = compute_cycle_id(
            t_ref=1_700_000_000.0, runner="run_cycle_once", version="v1"
        )
        assert isinstance(cid, str)
        assert len(cid) == 64
        assert all(c in "0123456789abcdef" for c in cid)

    def test_deterministic(self):
        kwargs = dict(t_ref=1_700_000_000.0, runner="run_cycle_once", version="v1")
        assert compute_cycle_id(**kwargs) == compute_cycle_id(**kwargs)

    def test_different_t_ref_different_id(self):
        a = compute_cycle_id(t_ref=1_700_000_000.0, runner="r", version="v1")
        b = compute_cycle_id(t_ref=1_700_000_001.0, runner="r", version="v1")
        assert a != b

    def test_different_runner_different_id(self):
        a = compute_cycle_id(t_ref=1_000.0, runner="alpha", version="v1")
        b = compute_cycle_id(t_ref=1_000.0, runner="beta", version="v1")
        assert a != b

    def test_different_version_different_id(self):
        a = compute_cycle_id(t_ref=1_000.0, runner="r", version="v1")
        b = compute_cycle_id(t_ref=1_000.0, runner="r", version="v2")
        assert a != b

    def test_fractional_t_ref_truncated_to_int(self):
        # t_ref is cast to int() in the payload — 1000.9 and 1000.1 both → 1000
        a = compute_cycle_id(t_ref=1000.1, runner="r", version="v1")
        b = compute_cycle_id(t_ref=1000.9, runner="r", version="v1")
        assert a == b

    def test_zero_t_ref(self):
        cid = compute_cycle_id(t_ref=0.0, runner="r", version="v1")
        assert len(cid) == 64


# ---------------------------------------------------------------------------
# is_valid_field_cycle
# ---------------------------------------------------------------------------


class TestIsValidFieldCycle:
    @pytest.mark.parametrize("value", ["init", "bootstrap", "computed"])
    def test_canonical_values_valid(self, value):
        assert is_valid_field_cycle(value) is True

    @pytest.mark.parametrize("value", ["unknown", "INIT", "diurnal", "", "null"])
    def test_non_canonical_invalid(self, value):
        assert is_valid_field_cycle(value) is False


# ---------------------------------------------------------------------------
# find_invalid_field_cycles
# ---------------------------------------------------------------------------


class TestFindInvalidFieldCycles:
    def test_all_valid_returns_empty_set(self):
        result = find_invalid_field_cycles(["init", "bootstrap", "computed"])
        assert result == set()

    def test_mixed_returns_only_invalids(self):
        result = find_invalid_field_cycles(["init", "bad", "computed", "wrong"])
        assert result == {"bad", "wrong"}

    def test_empty_input(self):
        assert find_invalid_field_cycles([]) == set()

    def test_all_invalid(self):
        result = find_invalid_field_cycles(["x", "y", "z"])
        assert result == {"x", "y", "z"}

    def test_canonical_field_cycles_constant(self):
        assert CANONICAL_FIELD_CYCLES == {"init", "bootstrap", "computed"}
