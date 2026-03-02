"""
Tests for rhythm_os.domain.antifragile

Modules covered:
- brittleness.py  (clamp01, compute_brittleness_index)
- drift.py        (compute_drift_index)
- strain.py       (clamp01, compute_strain_index)
- state.py        (compute_antifragile_state)

Invariants:
- All indices are in [0, 1]
- Missing / undefined inputs max out the corresponding component
- Monotonicity: higher stress → higher index
- compute_antifragile_state returns all four keys
- Pure functions: same input → same output
"""

from __future__ import annotations

import pytest

from rhythm_os.domain.antifragile.brittleness import (
    clamp01 as b_clamp01,
    compute_brittleness_index,
)
from rhythm_os.domain.antifragile.drift import compute_drift_index
from rhythm_os.domain.antifragile.strain import (
    clamp01 as s_clamp01,
    compute_strain_index,
)
from rhythm_os.domain.antifragile.state import compute_antifragile_state


# ------------------------------------------------------------------
# clamp01 (shared utility — both brittleness and strain expose one)
# ------------------------------------------------------------------


class TestClamp01:
    @pytest.mark.parametrize("fn", [b_clamp01, s_clamp01])
    def test_below_zero_clamps_to_zero(self, fn):
        assert fn(-10.0) == 0.0

    @pytest.mark.parametrize("fn", [b_clamp01, s_clamp01])
    def test_above_one_clamps_to_one(self, fn):
        assert fn(2.0) == 1.0

    @pytest.mark.parametrize("fn", [b_clamp01, s_clamp01])
    def test_zero_is_zero(self, fn):
        assert fn(0.0) == 0.0

    @pytest.mark.parametrize("fn", [b_clamp01, s_clamp01])
    def test_one_is_one(self, fn):
        assert fn(1.0) == 1.0

    @pytest.mark.parametrize("fn", [b_clamp01, s_clamp01])
    def test_midpoint_passthrough(self, fn):
        assert fn(0.5) == pytest.approx(0.5)


# ------------------------------------------------------------------
# compute_brittleness_index
# ------------------------------------------------------------------


class TestBrittlenessIndex:
    def test_in_range_for_full_state(self):
        result = compute_brittleness_index(
            {"irreversible_commitments": 4, "dependency_gaps": 3},
            unknowns_index=0.5,
        )
        assert 0.0 <= result <= 1.0

    def test_missing_commitments_maxes_out(self):
        # Missing key → treated as total_commitment_slots → C=1.0
        result = compute_brittleness_index({}, unknowns_index=0.0)
        assert result == pytest.approx(1.0)

    def test_missing_gaps_maxes_out(self):
        result = compute_brittleness_index(
            {"irreversible_commitments": 0},
            unknowns_index=0.0,
        )
        assert result == pytest.approx(1.0)

    def test_zero_everything_returns_zero(self):
        result = compute_brittleness_index(
            {"irreversible_commitments": 0, "dependency_gaps": 0},
            unknowns_index=0.0,
        )
        assert result == pytest.approx(0.0)

    def test_envelope_is_max_of_components(self):
        # unknowns_index = 0.8 dominates
        result = compute_brittleness_index(
            {"irreversible_commitments": 1, "dependency_gaps": 1},
            unknowns_index=0.8,
            total_commitment_slots=8,
            total_dependency_checks=6,
        )
        assert result >= 0.8

    def test_pure_deterministic(self):
        state = {"irreversible_commitments": 3, "dependency_gaps": 2}
        r1 = compute_brittleness_index(state, unknowns_index=0.6)
        r2 = compute_brittleness_index(state, unknowns_index=0.6)
        assert r1 == r2

    def test_higher_unknowns_higher_index(self):
        state = {"irreversible_commitments": 2, "dependency_gaps": 1}
        low = compute_brittleness_index(state, unknowns_index=0.1)
        high = compute_brittleness_index(state, unknowns_index=0.9)
        assert high > low


# ------------------------------------------------------------------
# compute_drift_index
# ------------------------------------------------------------------


class TestDriftIndex:
    def test_empty_baseline_returns_one(self):
        assert compute_drift_index(5.0, []) == 1.0

    def test_identical_baseline_zero_drift(self):
        # baseline with zero std → current == mean → drift = 0
        assert compute_drift_index(3.0, [3.0, 3.0, 3.0]) == pytest.approx(0.0)

    def test_far_from_baseline_high_drift(self):
        # Need a baseline with actual variance; [0,1,2,3] has std≈1.118
        # current=50 deviates far enough to saturate at 1.0
        baseline = [0.0, 1.0, 2.0, 3.0]
        result = compute_drift_index(50.0, baseline)
        assert result == pytest.approx(1.0)

    def test_result_in_range(self):
        for current in [-5.0, 0.0, 5.0, 100.0]:
            result = compute_drift_index(current, [1.0, 2.0, 3.0])
            assert 0.0 <= result <= 1.0

    def test_close_to_baseline_low_drift(self):
        baseline = [10.0, 11.0, 9.0, 10.5]
        result = compute_drift_index(10.2, baseline)
        assert result < 0.3

    def test_pure_deterministic(self):
        b = [1.0, 2.0, 3.0]
        r1 = compute_drift_index(5.0, b)
        r2 = compute_drift_index(5.0, b)
        assert r1 == r2


# ------------------------------------------------------------------
# compute_strain_index
# ------------------------------------------------------------------


class TestStrainIndex:
    def test_none_load_returns_one(self):
        assert compute_strain_index(recent_load=None, load_history=[1.0, 2.0]) == 1.0

    def test_empty_history_returns_one(self):
        assert compute_strain_index(recent_load=0.5, load_history=[]) == 1.0

    def test_both_none_returns_one(self):
        assert compute_strain_index(recent_load=None, load_history=None) == 1.0

    def test_low_load_low_strain(self):
        result = compute_strain_index(recent_load=0.1, load_history=[0.1, 0.1, 0.1])
        assert result < 0.2

    def test_high_load_high_strain(self):
        result = compute_strain_index(recent_load=1.0, load_history=[0.9, 1.0, 0.95])
        assert result >= 0.9

    def test_rest_factor_reduces_strain(self):
        base = compute_strain_index(recent_load=0.8, load_history=[0.8, 0.8])
        rested = compute_strain_index(
            recent_load=0.8, load_history=[0.8, 0.8], rest_factor=0.5
        )
        assert rested < base

    def test_result_in_range(self):
        for load in [0.0, 0.3, 0.6, 0.9, 1.5]:
            result = compute_strain_index(
                recent_load=load,
                load_history=[load, load, load],
            )
            assert 0.0 <= result <= 1.0

    def test_pure_deterministic(self):
        r1 = compute_strain_index(recent_load=0.7, load_history=[0.5, 0.6, 0.7])
        r2 = compute_strain_index(recent_load=0.7, load_history=[0.5, 0.6, 0.7])
        assert r1 == r2


# ------------------------------------------------------------------
# compute_antifragile_state
# ------------------------------------------------------------------


class TestAntifragileState:
    def test_returns_dict_with_all_keys(self):
        result = compute_antifragile_state(
            {
                "current_scalar": 5.0,
                "baseline_window": [4.0, 5.0, 6.0],
                "recent_load": 0.5,
                "load_history": [0.4, 0.5, 0.6],
                "unknowns_index": 0.3,
            }
        )
        for key in (
            "unknowns_index",
            "drift_index",
            "strain_index",
            "brittleness_index",
        ):
            assert key in result

    def test_all_values_in_range(self):
        result = compute_antifragile_state(
            {
                "current_scalar": 2.0,
                "baseline_window": [1.0, 2.0, 3.0],
                "recent_load": 0.4,
                "load_history": [0.3, 0.4, 0.5],
                "unknowns_index": 0.2,
            }
        )
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_empty_state_returns_maximal_indices(self):
        result = compute_antifragile_state({})
        # drift: empty baseline → 1.0; strain: None → 1.0; brittleness: missing → 1.0
        assert result["drift_index"] == pytest.approx(1.0)
        assert result["strain_index"] == pytest.approx(1.0)
        assert result["brittleness_index"] == pytest.approx(1.0)

    def test_unknowns_defaults_to_one(self):
        result = compute_antifragile_state({})
        assert result["unknowns_index"] == pytest.approx(1.0)

    def test_pure_deterministic(self):
        state = {
            "current_scalar": 3.0,
            "baseline_window": [2.0, 3.0, 4.0],
            "recent_load": 0.6,
            "load_history": [0.5, 0.6],
            "unknowns_index": 0.4,
        }
        r1 = compute_antifragile_state(state)
        r2 = compute_antifragile_state(state)
        assert r1 == r2
