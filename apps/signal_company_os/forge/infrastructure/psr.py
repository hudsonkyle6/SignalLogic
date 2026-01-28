from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PSREvent:
    """
    Observed events only.
    No intent, no prediction.
    """
    kind: str  # "ENDURANCE" | "SCAR" | "INTERVAL_OK" | "INTERVAL_FAIL"
    weight: float = 1.0


def compute_trust(events: List[PSREvent]) -> float:
    """
    Trust is observed history.
    - Endurance adds slowly
    - Scars subtract sharply
    - Interval outcomes adjust moderately
    """
    trust = 0.0
    for e in events:
        if e.kind == "ENDURANCE":
            trust += 1.0 * e.weight
        elif e.kind == "SCAR":
            trust -= 2.0 * e.weight
        elif e.kind == "INTERVAL_OK":
            trust += 0.5 * e.weight
        elif e.kind == "INTERVAL_FAIL":
            trust -= 1.0 * e.weight
    return trust


def scar_conditioning(trust: float, recent_scar_count: int) -> float:
    """
    Returns a scope multiplier in [0, 1].
    Recent scars narrow proposal scope immediately.
    Trust broadens scope gradually.
    """
    base = max(0.0, min(1.0, 0.5 + 0.05 * trust))
    penalty = min(0.5, 0.25 * recent_scar_count)
    return max(0.0, base - penalty)
def get_recent_scar_weights(
    psr_events,
    *,
    decay_rate: float = 0.1,
    lookback: int = 30,
):
    """
    Compute decayed scar weights from recent PSR events.

    Descriptive only:
    - No thresholds
    - No decisions
    - Higher weight = more recent / severe scar

    Returns: list[float]
    """
    weights = []
    age = 0

    for e in reversed(psr_events[-lookback:]):
        event_type = e.get("event") if isinstance(e, dict) else getattr(e, "event", None)

        if event_type in ("INTERVAL_FAILED", "GATE_DENIED"):
            weights.append((1.0 - decay_rate) ** age)

        age += 1

    return weights
