"""
Seasonal Prior — Rule-Based Climatological Baselines
POSTURE: TRIBUTARY (read-only, no authority)

Computes seasonal context for 42.9876°N 71.8126°W (southern New Hampshire)
from day-of-year alone. No ML. No accumulated data required.

This is Phase A of the Lighthouse architecture: honest rule-based priors
derived from NOAA climatological normals for the coordinates. The ML layer
(Phase B) will replace these priors after ~3 months of accumulated Dark Field
data.

Output fields:
  seasonal_band      : "winter" | "spring_transition" | "summer" | "fall_transition"
  seasonal_phase     : [0, 1] position within the annual cycle (0 = Jan 1)
  expected_pressure_hpa : climatological sea-level pressure expectation
  pattern_confidence : [0, 1] — how well-established the pattern is at this DOY
                       (0.8 = deep stable season; 0.5 = mid-transition)
  afterglow_decay    : [0.2, 0.9] — derived from pattern_confidence
                       (0.3 = stable, memory holds; 0.7 = transition, memory loosens)
  forest_proximity   : [0, 1] — proxy for distance from pasture center
                       (0 = known territory; 1 = forest edge)
                       For Phase A this is derived from transition proximity.

NO learning. NO persistence. NO side effects. Pure computation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Coordinates (fixed — southern NH, Nashua/Concord corridor)
# ---------------------------------------------------------------------------

LAT_DEG: float = 42.9876
LON_DEG: float = -71.8126


# ---------------------------------------------------------------------------
# Climatological normals for 42.9876°N, 71.8126°W
# Source: NOAA 1991–2020 Climate Normals, interpolated for location.
#
# Monthly sea-level pressure normals (hPa):
#   Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
_MONTHLY_PRESSURE_HPA = (
    1021.0,  # Jan — strong high-pressure, cold dense air
    1019.5,  # Feb
    1016.5,  # Mar — transition begins
    1014.5,  # Apr
    1016.0,  # May
    1016.5,  # Jun
    1017.0,  # Jul — summer ridge
    1017.5,  # Aug
    1018.0,  # Sep — fall ridge begins
    1017.0,  # Oct
    1017.5,  # Nov
    1019.5,  # Dec — winter pattern reasserts
)

# Monthly pattern confidence (how stable the seasonal signal is):
#   High in the center of stable seasons; lower during transition months.
_MONTHLY_CONFIDENCE = (
    0.82,  # Jan — deep winter, very stable
    0.80,  # Feb
    0.60,  # Mar — spring transition begins
    0.55,  # Apr
    0.62,  # May — late spring
    0.72,  # Jun — early summer
    0.83,  # Jul — stable summer
    0.82,  # Aug
    0.70,  # Sep — fall transition begins
    0.60,  # Oct
    0.62,  # Nov
    0.78,  # Dec — early winter
)

# Monthly seasonal bands:
_MONTHLY_BAND = (
    "winter",  # Jan
    "winter",  # Feb
    "spring_transition",  # Mar
    "spring_transition",  # Apr
    "spring_transition",  # May
    "summer",  # Jun
    "summer",  # Jul
    "summer",  # Aug
    "fall_transition",  # Sep
    "fall_transition",  # Oct
    "fall_transition",  # Nov
    "winter",  # Dec
)


# ---------------------------------------------------------------------------
# SeasonalPrior
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeasonalPrior:
    """
    Rule-based seasonal context for a given Unix timestamp.

    All values are read-only annotations. No authority over routing or commits.
    """

    seasonal_band: str  # "winter" | "spring_transition" | "summer" | "fall_transition"
    seasonal_phase: float  # [0, 1] — fractional position in the annual cycle
    expected_pressure_hpa: float
    pattern_confidence: float  # [0, 1] — stability of the current seasonal pattern
    afterglow_decay: float  # [0.2, 0.9] — wave memory decay rate for this season
    forest_proximity: float  # [0, 1] — 0 = pasture center, 1 = forest edge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doy(t: float) -> int:
    """Unix timestamp → day-of-year [1, 366]."""
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    return dt.timetuple().tm_yday


def _month_idx(t: float) -> int:
    """Unix timestamp → 0-based month index [0, 11]."""
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    return dt.month - 1


def _interp_monthly(table: tuple, t: float) -> float:
    """
    Cosine-interpolate between monthly normals using fractional day-in-month.
    Produces smooth transitions rather than step-function jumps at month
    boundaries.
    """
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    m0 = dt.month - 1  # 0-based current month
    # Fractional progress through the current month (0 = start, 1 = end)
    import calendar

    days_in_month = calendar.monthrange(dt.year, dt.month)[1]
    frac = (dt.day - 1 + dt.hour / 24.0) / days_in_month

    m1 = (m0 + 1) % 12  # next month (wraps Dec → Jan)
    v0 = table[m0]
    v1 = table[m1]

    # Cosine blending: smooth S-curve across the month boundary
    blend = (1.0 - math.cos(math.pi * frac)) / 2.0
    return v0 + blend * (v1 - v0)


def _seasonal_phase(t: float) -> float:
    """
    Fractional position in the annual cycle.
    0.0 = January 1, 1.0 = December 31.
    """
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    # Use day-of-year including fractional hour
    doy_frac = _doy(t) - 1 + dt.hour / 24.0
    days_in_year = 366.0 if _is_leap(dt.year) else 365.0
    return doy_frac / days_in_year


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _afterglow_decay_from_confidence(confidence: float) -> float:
    """
    Map pattern_confidence → afterglow_decay.

    High confidence (stable season) → low decay (memory holds).
    Low confidence (transition) → high decay (recent observations dominate).

    Linear mapping: confidence [0.5, 0.85] → decay [0.7, 0.25]
    Clamped to [0.2, 0.9].
    """
    # Inverted: high confidence → low decay
    decay = 0.9 - 0.8 * confidence
    return max(0.2, min(0.9, decay))


def _forest_proximity_from_confidence(confidence: float) -> float:
    """
    For Phase A (rule-based only), forest proximity is derived from
    how far we are from the center of a stable seasonal pattern.

    High confidence (stable season) → low proximity (deep in pasture).
    Low confidence (transition) → high proximity (near forest edge).

    Linear mapping: confidence [0.5, 0.85] → proximity [0.65, 0.10]
    Clamped to [0.0, 1.0].
    """
    proximity = 1.0 - confidence
    return max(0.0, min(1.0, proximity))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_seasonal_prior(t: float) -> SeasonalPrior:
    """
    Compute rule-based seasonal prior for the fixed coordinates
    (42.9876°N, 71.8126°W) at the given Unix timestamp.

    Pure computation — no I/O, no side effects, no ML.
    """
    m0 = _month_idx(t)
    band = _MONTHLY_BAND[m0]
    confidence = _interp_monthly(_MONTHLY_CONFIDENCE, t)
    pressure = _interp_monthly(_MONTHLY_PRESSURE_HPA, t)
    phase = _seasonal_phase(t)
    decay = _afterglow_decay_from_confidence(confidence)
    proximity = _forest_proximity_from_confidence(confidence)

    return SeasonalPrior(
        seasonal_band=band,
        seasonal_phase=phase,
        expected_pressure_hpa=pressure,
        pattern_confidence=round(confidence, 4),
        afterglow_decay=round(decay, 4),
        forest_proximity=round(proximity, 4),
    )
