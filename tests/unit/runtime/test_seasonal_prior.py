"""
Tests for rhythm_os.runtime.seasonal_prior

Invariants:
- seasonal_phase is in [0, 1] for any timestamp
- seasonal_band is one of the four valid bands
- expected_pressure_hpa is in a plausible range for the coordinates
- pattern_confidence is in [0, 1]
- afterglow_decay is in [0.2, 0.9]
- forest_proximity is in [0, 1]
- High-confidence months (deep winter/summer) have lower forest_proximity than transition months
- High-confidence months have lower afterglow_decay (memory holds longer)
- compute_seasonal_prior is pure (same input → same output)
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from rhythm_os.runtime.seasonal_prior import (
    compute_seasonal_prior,
    SeasonalPrior,
    _doy,
    _seasonal_phase,
    _afterglow_decay_from_confidence,
    _forest_proximity_from_confidence,
)


# Representative timestamps for each month (2025)
def _ts(month: int, day: int = 15) -> float:
    return datetime(2025, month, day, 12, 0, 0, tzinfo=timezone.utc).timestamp()


WINTER_TS = _ts(1)  # January — deep winter, stable
SPRING_TS = _ts(4)  # April — spring transition
SUMMER_TS = _ts(7)  # July — deep summer, stable
FALL_TS = _ts(10)  # October — fall transition


# ------------------------------------------------------------------
# _doy
# ------------------------------------------------------------------


class TestDoy:
    def test_january_1(self):
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert _doy(ts) == 1

    def test_december_31(self):
        ts = datetime(2025, 12, 31, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert _doy(ts) == 365

    def test_july_is_mid_year(self):
        ts = datetime(2025, 7, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert 180 <= _doy(ts) <= 185


# ------------------------------------------------------------------
# _seasonal_phase
# ------------------------------------------------------------------


class TestSeasonalPhase:
    def test_january_1_near_zero(self):
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert _seasonal_phase(ts) == pytest.approx(0.0, abs=0.01)

    def test_phase_in_range(self):
        for month in range(1, 13):
            ts = _ts(month)
            p = _seasonal_phase(ts)
            assert 0.0 <= p <= 1.0, f"phase out of range for month {month}: {p}"

    def test_phase_increases_monotonically(self):
        phases = [_seasonal_phase(_ts(m)) for m in range(1, 13)]
        for i in range(len(phases) - 1):
            assert phases[i] < phases[i + 1]


# ------------------------------------------------------------------
# _afterglow_decay_from_confidence
# ------------------------------------------------------------------


class TestAfterglowDecay:
    def test_high_confidence_low_decay(self):
        assert _afterglow_decay_from_confidence(0.85) <= 0.35

    def test_low_confidence_high_decay(self):
        assert _afterglow_decay_from_confidence(0.50) >= 0.45

    def test_always_in_range(self):
        for c in [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 1.0]:
            d = _afterglow_decay_from_confidence(c)
            assert 0.2 <= d <= 0.9, f"decay {d} out of range for confidence {c}"

    def test_monotonically_decreasing(self):
        # Higher confidence → lower decay
        d_high = _afterglow_decay_from_confidence(0.82)
        d_low = _afterglow_decay_from_confidence(0.55)
        assert d_high < d_low


# ------------------------------------------------------------------
# _forest_proximity_from_confidence
# ------------------------------------------------------------------


class TestForestProximity:
    def test_high_confidence_low_proximity(self):
        assert _forest_proximity_from_confidence(0.85) <= 0.20

    def test_low_confidence_high_proximity(self):
        assert _forest_proximity_from_confidence(0.50) >= 0.45

    def test_always_in_range(self):
        for c in [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 1.0]:
            p = _forest_proximity_from_confidence(c)
            assert 0.0 <= p <= 1.0, f"proximity {p} out of range for confidence {c}"


# ------------------------------------------------------------------
# compute_seasonal_prior
# ------------------------------------------------------------------


class TestComputeSeasonalPrior:
    def test_returns_seasonal_prior_dataclass(self):
        result = compute_seasonal_prior(WINTER_TS)
        assert isinstance(result, SeasonalPrior)

    def test_all_fields_present(self):
        result = compute_seasonal_prior(SUMMER_TS)
        assert result.seasonal_band is not None
        assert result.seasonal_phase is not None
        assert result.expected_pressure_hpa is not None
        assert result.pattern_confidence is not None
        assert result.afterglow_decay is not None
        assert result.forest_proximity is not None

    def test_seasonal_phase_in_range(self):
        for ts in [WINTER_TS, SPRING_TS, SUMMER_TS, FALL_TS]:
            r = compute_seasonal_prior(ts)
            assert 0.0 <= r.seasonal_phase <= 1.0

    def test_pressure_in_plausible_range(self):
        for ts in [WINTER_TS, SPRING_TS, SUMMER_TS, FALL_TS]:
            r = compute_seasonal_prior(ts)
            assert 1005.0 <= r.expected_pressure_hpa <= 1030.0, (
                f"Pressure {r.expected_pressure_hpa} out of range for ts={ts}"
            )

    def test_confidence_in_range(self):
        for ts in [WINTER_TS, SPRING_TS, SUMMER_TS, FALL_TS]:
            r = compute_seasonal_prior(ts)
            assert 0.0 <= r.pattern_confidence <= 1.0

    def test_afterglow_decay_in_range(self):
        for ts in [WINTER_TS, SPRING_TS, SUMMER_TS, FALL_TS]:
            r = compute_seasonal_prior(ts)
            assert 0.2 <= r.afterglow_decay <= 0.9

    def test_forest_proximity_in_range(self):
        for ts in [WINTER_TS, SPRING_TS, SUMMER_TS, FALL_TS]:
            r = compute_seasonal_prior(ts)
            assert 0.0 <= r.forest_proximity <= 1.0

    def test_winter_band(self):
        result = compute_seasonal_prior(WINTER_TS)
        assert result.seasonal_band == "winter"

    def test_spring_transition_band(self):
        result = compute_seasonal_prior(SPRING_TS)
        assert result.seasonal_band == "spring_transition"

    def test_summer_band(self):
        result = compute_seasonal_prior(SUMMER_TS)
        assert result.seasonal_band == "summer"

    def test_fall_transition_band(self):
        result = compute_seasonal_prior(FALL_TS)
        assert result.seasonal_band == "fall_transition"

    def test_pure_computation_deterministic(self):
        ts = WINTER_TS
        r1 = compute_seasonal_prior(ts)
        r2 = compute_seasonal_prior(ts)
        assert r1 == r2

    def test_stable_seasons_have_lower_forest_proximity(self):
        # Deep winter and deep summer should have lower proximity than transitions
        winter = compute_seasonal_prior(WINTER_TS)
        spring = compute_seasonal_prior(SPRING_TS)
        summer = compute_seasonal_prior(SUMMER_TS)
        fall = compute_seasonal_prior(FALL_TS)
        assert winter.forest_proximity < spring.forest_proximity
        assert summer.forest_proximity < fall.forest_proximity

    def test_stable_seasons_have_lower_afterglow_decay(self):
        winter = compute_seasonal_prior(WINTER_TS)
        spring = compute_seasonal_prior(SPRING_TS)
        summer = compute_seasonal_prior(SUMMER_TS)
        fall = compute_seasonal_prior(FALL_TS)
        assert winter.afterglow_decay < spring.afterglow_decay
        assert summer.afterglow_decay < fall.afterglow_decay

    def test_december_is_winter(self):
        dec_ts = _ts(12)
        result = compute_seasonal_prior(dec_ts)
        assert result.seasonal_band == "winter"
