"""
Derived Ocean Signals — Pure Physics Layer

Converts raw buoy telemetry into stable physical oscillators for the
Natural domain.  No IO.  No persistence.  No inference.

Target signal set (all normalized to [0, 1]):
    wave_energy         deep-water wave energy density (J/m²)
    wave_period         dominant wave period (seconds)
    wind_vector_x       eastward wind component
    wind_vector_y       northward wind component
    pressure_gradient   rate of barometric pressure change (hPa/sample)
    surface_temp        sea surface temperature (°C)

Authority: domain physics only — no thresholds, no interpretation.
"""

from __future__ import annotations

import math
from typing import List, Tuple

# -------------------------------------------------------------------
# Physical constants
# -------------------------------------------------------------------

_RHO: float = 1025.0   # seawater density (kg/m³)
_G: float = 9.81       # gravitational acceleration (m/s²)

# -------------------------------------------------------------------
# Normalization bounds
# -------------------------------------------------------------------

# Wave energy (J/m²) — calm sea ≈ 0, extreme storm ≈ ~200 kJ/m²
_E_MAX: float = 200_000.0

# Wave period (seconds) — swell range 2–25 s
_T_MIN: float = 2.0
_T_MAX: float = 25.0
_T_SPAN: float = _T_MAX - _T_MIN

# Wind speed (m/s) — calm to hurricane-force ~60 m/s
_W_MAX: float = 60.0

# Surface temperature (°C)
_ST_LOW: float = -2.0
_ST_HIGH: float = 35.0
_ST_SPAN: float = _ST_HIGH - _ST_LOW

# Pressure gradient (hPa/sample) — ±5 hPa/sample covers most events
_PG_MAX: float = 5.0


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# -------------------------------------------------------------------
# Derivation functions
# -------------------------------------------------------------------


def wave_energy(h_sig_m: float) -> float:
    """
    Deep-water wave energy density.

    E = (1/8) * rho * g * H²

    Args:
        h_sig_m: significant wave height (metres)

    Returns:
        Wave energy in J/m²  (non-negative)
    """
    if h_sig_m < 0.0:
        h_sig_m = 0.0
    return 0.125 * _RHO * _G * h_sig_m ** 2


def normalize_wave_energy(energy_j_m2: float) -> float:
    """Normalize wave energy to [0, 1] against the reference maximum."""
    return _clamp(energy_j_m2 / _E_MAX)


def normalize_wave_period(period_s: float) -> float:
    """Normalize wave period (seconds) to [0, 1]."""
    return _clamp((period_s - _T_MIN) / _T_SPAN)


def wind_vector(speed_m_s: float, direction_deg: float) -> Tuple[float, float]:
    """
    Decompose wind into Cartesian components.

    Convention: meteorological direction — wind *from* that bearing.
    vx > 0 → eastward component; vy > 0 → northward component.

    Args:
        speed_m_s:     wind speed in m/s
        direction_deg: direction wind is coming FROM (degrees, 0=N, 90=E)

    Returns:
        (vx, vy) in m/s
    """
    rad = math.radians(direction_deg)
    vx = -speed_m_s * math.sin(rad)   # eastward
    vy = -speed_m_s * math.cos(rad)   # northward
    return vx, vy


def normalize_wind_component(v_m_s: float) -> float:
    """
    Normalize a signed wind component to [0, 1].

    Maps [-W_MAX, +W_MAX] → [0, 1] with 0 m/s at 0.5.
    """
    return _clamp((v_m_s + _W_MAX) / (2.0 * _W_MAX))


def pressure_gradient(pressures: List[float]) -> List[float]:
    """
    Compute first-order pressure gradient (diff) over a sequence.

    Args:
        pressures: ordered list of barometer readings (hPa)

    Returns:
        List of length len(pressures) − 1 containing Δp per step.
        Returns [0.0] when fewer than 2 readings are supplied.
    """
    if len(pressures) < 2:
        return [0.0]
    return [pressures[i] - pressures[i - 1] for i in range(1, len(pressures))]


def normalize_pressure_gradient(delta_hpa: float) -> float:
    """
    Normalize a pressure gradient value to [0, 1].

    Maps [−PG_MAX, +PG_MAX] → [0, 1] with 0 Δhpa at 0.5.
    Negative Δp (pressure drop → storm signal) maps below 0.5.
    """
    return _clamp((delta_hpa + _PG_MAX) / (2.0 * _PG_MAX))


def normalize_surface_temp(temp_c: float) -> float:
    """Normalize sea surface temperature (°C) to [0, 1]."""
    return _clamp((temp_c - _ST_LOW) / _ST_SPAN)
