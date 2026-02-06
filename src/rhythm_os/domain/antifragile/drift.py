# rhythm_os/domain/antifragile/drift.py

from typing import Sequence
import math


def compute_drift_index(
    current: float,
    baseline: Sequence[float],
    *,
    drift_scale: float = 3.0,
) -> float:
    """
    Compute normalized drift index (0–1) relative to a recent baseline.

    Normalization behavior:
    - Empty baseline → maximal normalized deviation (1.0)

    Notes:
    - Purely descriptive
    - No thresholds, decisions, or semantics
    - drift_scale is a dimensionless normalization constant
    """

    if not baseline:
        return 1.0

    n = len(baseline)
    mean = sum(baseline) / n

    variance = sum((x - mean) ** 2 for x in baseline) / n
    std = math.sqrt(variance)

    if std == 0:
        return 0.0  # zero dispersion in baseline

    deviation = abs(current - mean) / std
    return min(deviation / drift_scale, 1.0)
