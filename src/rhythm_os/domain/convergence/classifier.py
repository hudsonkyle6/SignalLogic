"""
ConvergenceClassifier — NOISE / COUPLING / LAG classification from observation history.

Classifies a domain pair's convergence pattern using three heuristics:

  NOISE     The pair consistently meets at the same phase bucket.
            Interpretation: shared daily rhythm, predictable entrainment.
            Threshold: dominant bucket contains >= NOISE_RATIO of all observations.
            Forward signal value: LOW — this is expected background behaviour.

  LAG       One domain consistently leads the other into convergence.
            Interpretation: domain A's signal precedes domain B's,
            suggesting directional influence or response latency.
            Threshold: one leading_domain accounts for >= LAG_RATIO of obs.
            Forward signal value: MEDIUM — directionality is informative.

  COUPLING  Convergence is real but neither phase-locked nor directionally led.
            Interpretation: irregular coupling — the pair co-moves without
            a fixed phase or leader.
            Forward signal value: HIGH — unexpected coupling is the strongest signal.

  UNKNOWN   Fewer than MIN_OBSERVATIONS have been recorded. Not enough data
            to distinguish signal from noise yet.

Classification is stateless — it operates on a list of ConvergenceObservations
and returns a ConvergenceType. It does not read from or write to the store.

Usage:
    classifier = ConvergenceClassifier()
    obs = store.get_history("natural", "system")
    result = classifier.classify(obs)
    print(result.convergence_type, result.confidence, result.rationale)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from rhythm_os.domain.convergence.memory_store import (
    ConvergenceObservation,
)


# ---------------------------------------------------------------------------
# Classification thresholds
# ---------------------------------------------------------------------------

# Minimum observations before any classification is attempted
MIN_OBSERVATIONS = 5

# Dominant bucket must hold >= this fraction of all observations → NOISE
NOISE_RATIO = 0.60

# One leading domain must appear >= this fraction of all observations → LAG
LAG_RATIO = 0.70


# ---------------------------------------------------------------------------
# ConvergenceType
# ---------------------------------------------------------------------------


class ConvergenceType(str, Enum):
    NOISE = "NOISE"
    COUPLING = "COUPLING"
    LAG = "LAG"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassificationResult:
    """
    Output of the classifier.

    convergence_type  The classification verdict
    confidence        Fraction that drove the classification (0.0-1.0).
                      For NOISE: dominant_bucket_count / total.
                      For LAG: leading_domain_count / total.
                      For COUPLING: 1.0 - max(NOISE ratio, LAG ratio).
                      For UNKNOWN: 0.0.
    rationale         One-sentence human-readable explanation
    dominant_bucket   Phase bucket that dominated (NOISE only, else None)
    leading_domain    Domain that led most often (LAG only, else None)
    observation_count Total observations used in classification
    """

    convergence_type: ConvergenceType
    confidence: float
    rationale: str
    dominant_bucket: Optional[int]
    leading_domain: Optional[str]
    observation_count: int


# ---------------------------------------------------------------------------
# ConvergenceClassifier
# ---------------------------------------------------------------------------


class ConvergenceClassifier:
    """
    Stateless classifier. Operates on a list of ConvergenceObservations.

    Threshold parameters are configurable at construction time so tests
    can exercise boundary conditions without monkeypatching globals.
    """

    def __init__(
        self,
        *,
        min_observations: int = MIN_OBSERVATIONS,
        noise_ratio: float = NOISE_RATIO,
        lag_ratio: float = LAG_RATIO,
    ) -> None:
        self._min_obs = min_observations
        self._noise_ratio = noise_ratio
        self._lag_ratio = lag_ratio

    def classify(
        self, observations: List[ConvergenceObservation]
    ) -> ClassificationResult:
        """
        Classify a domain pair's convergence pattern.

        Checks UNKNOWN → NOISE → LAG → COUPLING in that order.
        The first matching threshold wins.
        """
        n = len(observations)

        if n < self._min_obs:
            return ClassificationResult(
                convergence_type=ConvergenceType.UNKNOWN,
                confidence=0.0,
                rationale=f"insufficient data: {n} observations, need >= {self._min_obs}",
                dominant_bucket=None,
                leading_domain=None,
                observation_count=n,
            )

        bucket_counts = _count_buckets(observations)
        leading_counts = _count_leaders(observations)

        top_bucket = max(bucket_counts, key=lambda b: bucket_counts[b])
        top_bucket_ratio = bucket_counts[top_bucket] / n

        top_leader = max(leading_counts, key=lambda d: leading_counts[d])
        top_leader_ratio = leading_counts[top_leader] / n

        # NOISE — phase-locked to a dominant bucket
        if top_bucket_ratio >= self._noise_ratio:
            return ClassificationResult(
                convergence_type=ConvergenceType.NOISE,
                confidence=round(top_bucket_ratio, 4),
                rationale=(
                    f"phase-locked: {int(top_bucket_ratio * 100)}% of observations "
                    f"in bucket {top_bucket} (daily shared rhythm)"
                ),
                dominant_bucket=top_bucket,
                leading_domain=None,
                observation_count=n,
            )

        # LAG — one domain consistently leads
        if top_leader_ratio >= self._lag_ratio:
            return ClassificationResult(
                convergence_type=ConvergenceType.LAG,
                confidence=round(top_leader_ratio, 4),
                rationale=(
                    f"directional: '{top_leader}' leads convergence "
                    f"{int(top_leader_ratio * 100)}% of the time"
                ),
                dominant_bucket=None,
                leading_domain=top_leader,
                observation_count=n,
            )

        # COUPLING — real but irregular
        max_signal = max(top_bucket_ratio, top_leader_ratio)
        coupling_confidence = round(1.0 - max_signal, 4)
        return ClassificationResult(
            convergence_type=ConvergenceType.COUPLING,
            confidence=coupling_confidence,
            rationale=(
                f"irregular coupling across {len(bucket_counts)} buckets "
                f"with no dominant phase or leader"
            ),
            dominant_bucket=None,
            leading_domain=None,
            observation_count=n,
        )

    def classify_summary(self, summary: Dict) -> ClassificationResult:
        """
        Classify from a pair_summary() dict (avoids reloading raw observations).

        Useful when you have already called store.pair_summary().
        Reconstructs bucket/leading counts from the summary dict and applies
        the same thresholds.
        """
        n = summary.get("total_count", 0)
        if n < self._min_obs:
            return ClassificationResult(
                convergence_type=ConvergenceType.UNKNOWN,
                confidence=0.0,
                rationale=f"insufficient data: {n} observations, need >= {self._min_obs}",
                dominant_bucket=None,
                leading_domain=None,
                observation_count=n,
            )

        bucket_counts: Dict[int, int] = summary.get("bucket_counts", {})
        leading_counts: Dict[str, int] = summary.get("leading_counts", {})

        if not bucket_counts or not leading_counts:
            return ClassificationResult(
                convergence_type=ConvergenceType.UNKNOWN,
                confidence=0.0,
                rationale="summary missing bucket or leading counts",
                dominant_bucket=None,
                leading_domain=None,
                observation_count=n,
            )

        top_bucket = max(bucket_counts, key=lambda b: bucket_counts[b])
        top_bucket_ratio = bucket_counts[top_bucket] / n

        top_leader = max(leading_counts, key=lambda d: leading_counts[d])
        top_leader_ratio = leading_counts[top_leader] / n

        if top_bucket_ratio >= self._noise_ratio:
            return ClassificationResult(
                convergence_type=ConvergenceType.NOISE,
                confidence=round(top_bucket_ratio, 4),
                rationale=(
                    f"phase-locked: {int(top_bucket_ratio * 100)}% in bucket {top_bucket}"
                ),
                dominant_bucket=top_bucket,
                leading_domain=None,
                observation_count=n,
            )

        if top_leader_ratio >= self._lag_ratio:
            return ClassificationResult(
                convergence_type=ConvergenceType.LAG,
                confidence=round(top_leader_ratio, 4),
                rationale=(
                    f"directional: '{top_leader}' leads {int(top_leader_ratio * 100)}% of the time"
                ),
                dominant_bucket=None,
                leading_domain=top_leader,
                observation_count=n,
            )

        max_signal = max(top_bucket_ratio, top_leader_ratio)
        return ClassificationResult(
            convergence_type=ConvergenceType.COUPLING,
            confidence=round(1.0 - max_signal, 4),
            rationale="irregular coupling: no dominant phase or leader",
            dominant_bucket=None,
            leading_domain=None,
            observation_count=n,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_buckets(observations: List[ConvergenceObservation]) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for o in observations:
        counts[o.phase_bucket] = counts.get(o.phase_bucket, 0) + 1
    return counts


def _count_leaders(observations: List[ConvergenceObservation]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for o in observations:
        counts[o.leading_domain] = counts.get(o.leading_domain, 0) + 1
    return counts
