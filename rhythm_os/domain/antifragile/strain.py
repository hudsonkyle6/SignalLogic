# rhythm_os/domain/antifragile/strain.py

from typing import Sequence


def clamp01(x: float) -> float:
    """
    Project input to the unit interval [0, 1] via saturation.

    Pure geometric normalization — no thresholds, no decisions,
    no authority, and no evaluative semantics.
    """
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else x


def compute_strain_index(
    *,
    recent_load: float | None,
    load_history: Sequence[float] | None,
    rest_factor: float | None = None,
) -> float:
    """
    Compute a normalized index in [0, 1] from recent and historical
    reference values.

    Normalization rules:
    - Missing reference inputs (recent_load is None or load_history empty)
      → maximal normalized value (1.0)
    - Otherwise → envelope-based computation (see below)

    The raw value is the maximum of:
    - the most recent reference value
    - the arithmetic mean of the historical references

    This is a conservative envelope selection — not a stress,
    dominance, or evaluative judgment.

    The rest_factor is an external dimensionless attenuation coefficient
    supplied by the caller.
    It is NOT a recovery signal, rest-period proxy, or physiological variable.
    Default (None) → no attenuation (coefficient = 0.0).

    The final output is saturated to [0, 1].

    This function performs only dimensionless normalization.
    No physiological, evaluative, or decision semantics are implied
    or permitted.
    """

    if recent_load is None or not load_history:
        return 1.0

    mean_load = sum(load_history) / len(load_history)

    # Envelope selection: dominant magnitude between recent and baseline
    raw = max(recent_load, mean_load)

    # rest_factor is a caller-supplied dimensionless coefficient
    # — not a recovery or rest signal
    rest = rest_factor if rest_factor is not None else 0.0
    adjusted = raw * (1.0 - clamp01(rest))

    return clamp01(adjusted)
