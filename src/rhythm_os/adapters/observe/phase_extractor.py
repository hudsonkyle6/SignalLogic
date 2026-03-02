import math

try:
    import numpy as np
except ImportError as _e:
    raise ImportError(
        "numpy is required for phase extraction. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e
from typing import List, Tuple, Dict

try:
    from scipy.signal import hilbert

    _HILBERT_AVAILABLE = True
except Exception:
    _HILBERT_AVAILABLE = False


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _wrap_phase(phi: float) -> float:
    """Wrap phase to [0, 2π)."""
    return phi % (2.0 * math.pi)


# ---------------------------------------------------------
# Hilbert-based extractor
# ---------------------------------------------------------


def extract_phase_hilbert(
    samples: List[Tuple[float, float]],
) -> Tuple[float, Dict[str, str]]:
    """
    Extract instantaneous phase using Hilbert transform.

    samples: [(t, value), ...] ordered by time
    Returns: (phase_rad, metadata)
    """
    if not _HILBERT_AVAILABLE:
        raise RuntimeError("Hilbert transform not available (scipy missing).")

    if len(samples) < 8:
        raise ValueError("Insufficient samples for Hilbert phase extraction.")

    values = np.array([v for _, v in samples], dtype=float)

    analytic = hilbert(values)
    phase = np.angle(analytic[-1])

    return _wrap_phase(phase), {
        "method": "hilbert",
        "notes": "instantaneous phase from analytic signal",
    }


# ---------------------------------------------------------
# Zero-crossing extractor (robust fallback)
# ---------------------------------------------------------


def extract_phase_zero_crossing(
    samples: List[Tuple[float, float]],
) -> Tuple[float, Dict[str, str]]:
    """
    Estimate phase from most recent zero crossing.

    Assumes quasi-periodic signal.
    """
    if len(samples) < 4:
        raise ValueError("Insufficient samples for zero-crossing phase extraction.")

    # Find last two zero crossings
    crossings = []
    for i in range(1, len(samples)):
        v0 = samples[i - 1][1]
        v1 = samples[i][1]
        if v0 == 0:
            crossings.append(samples[i - 1][0])
        elif v0 * v1 < 0:
            t0, t1 = samples[i - 1][0], samples[i][0]
            # linear interpolation
            frac = abs(v0) / (abs(v0) + abs(v1))
            crossings.append(t0 + frac * (t1 - t0))

    if len(crossings) < 2:
        raise ValueError("Not enough zero crossings to estimate phase.")

    t_last, t_prev = crossings[-1], crossings[-2]
    period = t_last - t_prev
    if period <= 0:
        raise ValueError("Invalid period from zero crossings.")

    t_now = samples[-1][0]
    phase = 2.0 * math.pi * (t_now - t_last) / period

    return _wrap_phase(phase), {
        "method": "zero_crossing",
        "notes": "linear interpolation between sign changes",
    }


# ---------------------------------------------------------
# Unified interface
# ---------------------------------------------------------


def extract_external_phase(
    samples: List[Tuple[float, float]],
    method: str = "hilbert",
) -> Tuple[float, Dict[str, str]]:
    """
    Unified external phase extractor.

    method: 'hilbert' | 'zero_crossing'
    """
    if method == "hilbert":
        return extract_phase_hilbert(samples)

    if method == "zero_crossing":
        return extract_phase_zero_crossing(samples)

    raise ValueError(f"Unknown phase extraction method: {method}")
