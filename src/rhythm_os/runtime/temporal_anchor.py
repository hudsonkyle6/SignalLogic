"""
Temporal Anchor — Rhythmic Reference Frame

Computes the system's position within three natural oscillatory cycles:
  - Long wave    (~28 days, Mf tidal constituent)
  - Diurnal      (24 hours, K1 constituent)
  - Semi-diurnal (12 hours, M2 dominant, S2 solar)

These anchors provide a shared temporal reference frame across all signal
domains. Every packet entering the system carries its phase position within
each cycle, enabling the Turbine to detect cross-domain convergence.

All phases are in [0.0, 1.0] representing fractional position in the cycle
(0.0 = cycle start, 0.5 = cycle midpoint, 1.0 = cycle end/next start).

NO authority. NO side effects. Pure computation only.
"""

from __future__ import annotations

from dataclasses import dataclass


# ------------------------------------------------------------
# Cycle periods (seconds)
# ------------------------------------------------------------

LONG_WAVE_PERIOD_S: float = 28.0 * 24.0 * 3600.0  # Mf constituent (~28 day)
DIURNAL_PERIOD_S: float = 24.0 * 3600.0             # K1 constituent (24 h)
SEMI_DIURNAL_PERIOD_S: float = 12.0 * 3600.0        # M2 constituent (12 h)

# Frequencies (Hz)
LONG_WAVE_HZ: float = 1.0 / LONG_WAVE_PERIOD_S
DIURNAL_HZ: float = 1.0 / DIURNAL_PERIOD_S
SEMI_DIURNAL_HZ: float = 1.0 / SEMI_DIURNAL_PERIOD_S

# Domain → dominant anchor frequency
_DOMAIN_DOMINANT_HZ: dict[str, float] = {
    "natural":     SEMI_DIURNAL_HZ,   # atmospheric/tidal 12h rhythm
    "environment": SEMI_DIURNAL_HZ,
    "system":      DIURNAL_HZ,        # operational daily rhythm
    "ops":         DIURNAL_HZ,
    "internal":    DIURNAL_HZ,
    "market":      DIURNAL_HZ,        # trading-day rhythm
    "finance":     DIURNAL_HZ,
    "cyber":       DIURNAL_HZ,
    "project":     DIURNAL_HZ,
    "narrative":   LONG_WAVE_HZ,      # narrative/doctrinal long-wave
}

_DEFAULT_DOMINANT_HZ: float = DIURNAL_HZ


# ------------------------------------------------------------
# TemporalAnchor
# ------------------------------------------------------------

@dataclass(frozen=True)
class TemporalAnchor:
    """
    Immutable snapshot of the system's position in each anchor cycle
    at a given Unix timestamp.

    All phases in [0.0, 1.0].
    dominant_hz: the primary reference frequency for this domain.
    """

    t: float
    long_wave_phase: float
    diurnal_phase: float
    semi_diurnal_phase: float
    dominant_hz: float


# ------------------------------------------------------------
# Factory
# ------------------------------------------------------------

def compute_anchor(t: float, *, domain: str = "system") -> TemporalAnchor:
    """
    Compute temporal anchor phases from a Unix timestamp.

    Args:
        t:      Unix timestamp (seconds since epoch).
        domain: Signal domain name — selects the dominant frequency.

    Returns:
        TemporalAnchor with phase positions in [0.0, 1.0] for each cycle.
    """
    long_wave_phase = (t / LONG_WAVE_PERIOD_S) % 1.0
    diurnal_phase = (t / DIURNAL_PERIOD_S) % 1.0
    semi_diurnal_phase = (t / SEMI_DIURNAL_PERIOD_S) % 1.0

    dominant_hz = _DOMAIN_DOMINANT_HZ.get(
        (domain or "system").lower(),
        _DEFAULT_DOMINANT_HZ,
    )

    return TemporalAnchor(
        t=t,
        long_wave_phase=long_wave_phase,
        diurnal_phase=diurnal_phase,
        semi_diurnal_phase=semi_diurnal_phase,
        dominant_hz=dominant_hz,
    )
