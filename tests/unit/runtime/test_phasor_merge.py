"""
Tests for rhythm_os.core.phasor_merge

Covers:
- wrap_angle: wraps to (-pi, pi]
- project_samples_to_clocks: empty samples, zero magnitude, invalid clocks,
  single clock, multi-clock, group phasor properties, ClockProjection values
- GroupProjection / ClockProjection dataclass access
"""

from __future__ import annotations

import math

import pytest

from rhythm_os.core.phasor_merge import (
    ClockProjection,
    GroupProjection,
    project_samples_to_clocks,
    wrap_angle,
)

TAU = 2.0 * math.pi


# ---------------------------------------------------------------------------
# wrap_angle
# ---------------------------------------------------------------------------


class TestWrapAngle:
    def test_zero(self):
        assert wrap_angle(0.0) == pytest.approx(0.0)

    def test_pi_wraps_to_pi(self):
        # pi is the boundary — should stay at pi
        assert wrap_angle(math.pi) == pytest.approx(math.pi)

    def test_slightly_above_pi_wraps_negative(self):
        v = wrap_angle(math.pi + 0.01)
        assert v == pytest.approx(-math.pi + 0.01, abs=1e-9)

    def test_negative_pi_stays(self):
        v = wrap_angle(-math.pi)
        assert abs(v) == pytest.approx(math.pi)

    def test_two_pi_wraps_to_zero(self):
        assert wrap_angle(TAU) == pytest.approx(0.0, abs=1e-9)

    def test_large_positive(self):
        v = wrap_angle(5 * TAU + 0.5)
        assert v == pytest.approx(0.5, abs=1e-9)

    def test_large_negative(self):
        v = wrap_angle(-5 * TAU - 0.5)
        assert v == pytest.approx(-0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# project_samples_to_clocks — degenerate inputs
# ---------------------------------------------------------------------------


class TestProjectDegenerateInputs:
    def test_empty_samples(self):
        result = project_samples_to_clocks([], {"diurnal": 86400.0})
        assert isinstance(result, GroupProjection)
        assert result.coherence == 0.0
        assert result.phasor == 0j
        assert result.phase == 0.0
        assert result.clocks == {}

    def test_samples_with_zero_amplitude(self):
        # mag_sum = 0 → degenerate
        samples = [(0.0, 0.0), (3600.0, 0.0)]
        result = project_samples_to_clocks(samples, {"diurnal": 86400.0})
        assert result.coherence == 0.0
        assert result.clocks == {}

    def test_no_clocks(self):
        result = project_samples_to_clocks([(0.0, 1.0)], {})
        assert result.coherence == 0.0
        assert result.clocks == {}

    def test_invalid_clock_period_zero(self):
        # Period ≤ 0 is skipped
        result = project_samples_to_clocks([(0.0, 1.0)], {"bad": 0.0})
        assert result.coherence == 0.0
        assert result.clocks == {}

    def test_malformed_sample_is_skipped(self):
        # Non-numeric tuples are skipped; valid one remains
        samples = [("x", "y"), (0.0, 1.0)]
        result = project_samples_to_clocks(samples, {"diurnal": 86400.0})
        assert isinstance(result, GroupProjection)
        # At least one valid sample → clocks populated
        assert "diurnal" in result.clocks


# ---------------------------------------------------------------------------
# project_samples_to_clocks — single clock
# ---------------------------------------------------------------------------


class TestProjectSingleClock:
    def test_clock_projection_fields(self):
        T = 100.0
        samples = [(0.0, 1.0)]
        result = project_samples_to_clocks(samples, {"test": T})
        assert "test" in result.clocks
        cp: ClockProjection = result.clocks["test"]
        assert cp.period_s == pytest.approx(T)
        assert cp.omega == pytest.approx(TAU / T)
        assert 0.0 <= cp.coherence <= 1.0
        assert -math.pi <= cp.phase <= math.pi

    def test_single_sample_coherence_is_one(self):
        # With one sample of amplitude 1, Z = exp(j*phi) / 1 → |Z| = 1
        T = 100.0
        t = 25.0  # arbitrary time
        result = project_samples_to_clocks([(t, 1.0)], {"c": T})
        cp = result.clocks["c"]
        assert cp.coherence == pytest.approx(1.0, abs=1e-9)

    def test_perfect_alignment_coherence(self):
        # Multiple samples all at t=0 (same phase) → coherence = 1
        T = 100.0
        samples = [(0.0, 1.0), (0.0, 2.0), (0.0, 0.5)]
        result = project_samples_to_clocks(samples, {"c": T})
        cp = result.clocks["c"]
        assert cp.coherence == pytest.approx(1.0, abs=1e-9)

    def test_perfect_cancellation_coherence_zero(self):
        # Two equal-weight samples exactly half a period apart → phasors cancel
        T = 100.0
        samples = [(0.0, 1.0), (T / 2, 1.0)]  # phases differ by π
        result = project_samples_to_clocks(samples, {"c": T})
        cp = result.clocks["c"]
        assert cp.coherence == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# project_samples_to_clocks — multiple clocks
# ---------------------------------------------------------------------------


class TestProjectMultipleClocks:
    def test_group_phasor_is_mean_of_clock_phasors(self):
        clocks = {"a": 100.0, "b": 200.0}
        samples = [(0.0, 1.0)]
        result = project_samples_to_clocks(samples, clocks)
        expected_group = (result.clocks["a"].phasor + result.clocks["b"].phasor) / 2
        assert abs(result.phasor - expected_group) == pytest.approx(0.0, abs=1e-9)

    def test_all_clocks_present(self):
        clocks = {
            "diurnal": 86400.0,
            "semi_diurnal": 43200.0,
            "seasonal": 365.25 * 86400,
        }
        samples = [(float(i * 3600), 1.0) for i in range(24)]
        result = project_samples_to_clocks(samples, clocks)
        for name in clocks:
            assert name in result.clocks

    def test_group_coherence_bounded(self):
        clocks = {"a": 100.0, "b": 200.0}
        samples = [(float(i * 10), float(i + 1)) for i in range(20)]
        result = project_samples_to_clocks(samples, clocks)
        assert 0.0 <= result.coherence <= 1.0

    def test_group_phase_bounded(self):
        clocks = {"a": 100.0, "b": 300.0}
        samples = [(0.0, 1.0), (50.0, 0.5)]
        result = project_samples_to_clocks(samples, clocks)
        assert -math.pi <= result.phase <= math.pi


# ---------------------------------------------------------------------------
# Dataclass immutability
# ---------------------------------------------------------------------------


class TestDataclassImmutability:
    def test_clock_projection_frozen(self):
        cp = ClockProjection(
            period_s=100.0, omega=0.1, phasor=1 + 0j, coherence=1.0, phase=0.0
        )
        with pytest.raises((AttributeError, TypeError)):
            cp.coherence = 0.5  # type: ignore[misc]

    def test_group_projection_frozen(self):
        gp = GroupProjection(phasor=0j, coherence=0.0, phase=0.0, clocks={})
        with pytest.raises((AttributeError, TypeError)):
            gp.coherence = 0.5  # type: ignore[misc]
