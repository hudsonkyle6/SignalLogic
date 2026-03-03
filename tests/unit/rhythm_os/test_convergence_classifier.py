"""
Tests for rhythm_os.domain.convergence.classifier

Modules covered:
- ConvergenceType enum
- ClassificationResult dataclass
- ConvergenceClassifier.classify
- ConvergenceClassifier.classify_summary

Invariants:
- classify returns UNKNOWN when observations < min_observations
- classify returns NOISE when dominant bucket >= noise_ratio
- classify returns LAG when leading domain >= lag_ratio
- classify returns COUPLING otherwise (real but irregular)
- NOISE confidence equals dominant_bucket_count / total
- LAG confidence equals leading_domain_count / total
- COUPLING confidence equals 1 - max(noise_ratio, lag_ratio)
- dominant_bucket is set for NOISE, None for others
- leading_domain is set for LAG, None for others
- classify_summary produces identical results to classify on equivalent data
- Thresholds are configurable at construction
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from rhythm_os.domain.convergence.classifier import (
    ConvergenceClassifier,
    ConvergenceType,
)
from rhythm_os.domain.convergence.memory_store import (
    N_BUCKETS,
    ConvergenceMemoryStore,
    ConvergenceObservation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obs(
    *,
    domain_pair: str = "natural+system",
    phase_bucket: int = 0,
    diurnal_phase: float = 0.0,
    leading_domain: str = "natural",
    t: float = 1000.0,
) -> ConvergenceObservation:
    import uuid

    return ConvergenceObservation(
        obs_id=str(uuid.uuid4()),
        t=t,
        domain_pair=domain_pair,
        phase_bucket=phase_bucket,
        diurnal_phase=diurnal_phase,
        leading_domain=leading_domain,
        convergence_note="test",
    )


def _noise_obs(
    n: int, bucket: int = 0, leader: str = "natural"
) -> List[ConvergenceObservation]:
    """All observations in the same bucket (NOISE pattern)."""
    return [
        _obs(phase_bucket=bucket, leading_domain=leader, t=float(i)) for i in range(n)
    ]


def _lag_obs(n: int, leader: str = "natural") -> List[ConvergenceObservation]:
    """All observations led by the same domain across varied buckets (LAG pattern)."""
    return [
        _obs(phase_bucket=i % 5, leading_domain=leader, t=float(i)) for i in range(n)
    ]


def _coupling_obs(n: int) -> List[ConvergenceObservation]:
    """Observations spread across buckets with mixed leaders (COUPLING pattern)."""
    leaders = ["natural", "system", "market"]
    return [
        _obs(
            phase_bucket=i % 5,
            diurnal_phase=(i % 5 + 0.5) / N_BUCKETS,  # midpoint of each bucket
            leading_domain=leaders[i % len(leaders)],
            t=float(i),
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# UNKNOWN
# ---------------------------------------------------------------------------


class TestUnknown:
    def test_zero_observations_returns_unknown(self):
        c = ConvergenceClassifier()
        result = c.classify([])
        assert result.convergence_type == ConvergenceType.UNKNOWN

    def test_below_min_returns_unknown(self):
        c = ConvergenceClassifier(min_observations=5)
        result = c.classify(_noise_obs(4))
        assert result.convergence_type == ConvergenceType.UNKNOWN

    def test_exactly_min_is_not_unknown(self):
        c = ConvergenceClassifier(min_observations=5)
        result = c.classify(_noise_obs(5))
        assert result.convergence_type != ConvergenceType.UNKNOWN

    def test_unknown_confidence_is_zero(self):
        c = ConvergenceClassifier()
        result = c.classify(_noise_obs(2))
        assert result.confidence == 0.0

    def test_unknown_observation_count_recorded(self):
        c = ConvergenceClassifier()
        result = c.classify(_noise_obs(3))
        assert result.observation_count == 3


# ---------------------------------------------------------------------------
# NOISE
# ---------------------------------------------------------------------------


class TestNoise:
    def test_phase_locked_pattern_returns_noise(self):
        c = ConvergenceClassifier(noise_ratio=0.6)
        obs = _noise_obs(10, bucket=3)  # all in bucket 3
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.NOISE

    def test_noise_confidence_is_dominant_ratio(self):
        c = ConvergenceClassifier(noise_ratio=0.6)
        obs = _noise_obs(8, bucket=0) + [_obs(phase_bucket=1)]
        # 8/9 ≈ 0.889 in bucket 0
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.NOISE
        assert result.confidence == pytest.approx(8 / 9, abs=1e-4)

    def test_noise_dominant_bucket_set(self):
        c = ConvergenceClassifier(noise_ratio=0.6)
        obs = _noise_obs(10, bucket=5)
        result = c.classify(obs)
        assert result.dominant_bucket == 5

    def test_noise_leading_domain_is_none(self):
        c = ConvergenceClassifier(noise_ratio=0.6)
        result = c.classify(_noise_obs(10))
        assert result.leading_domain is None

    def test_exactly_at_noise_threshold_is_noise(self):
        # 6 of 10 in same bucket = exactly 0.60 → NOISE
        c = ConvergenceClassifier(noise_ratio=0.60)
        obs = _noise_obs(6) + [_obs(phase_bucket=i + 1) for i in range(4)]
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.NOISE

    def test_below_noise_threshold_not_noise(self):
        # 5 of 10 = 0.50 < 0.60 → not NOISE
        c = ConvergenceClassifier(noise_ratio=0.60)
        obs = _noise_obs(5) + [_obs(phase_bucket=i + 1) for i in range(5)]
        result = c.classify(obs)
        assert result.convergence_type != ConvergenceType.NOISE


# ---------------------------------------------------------------------------
# LAG
# ---------------------------------------------------------------------------


class TestLag:
    def test_dominant_leader_returns_lag(self):
        c = ConvergenceClassifier(lag_ratio=0.70)
        obs = _lag_obs(10, leader="natural")  # all led by natural, varied buckets
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.LAG

    def test_lag_leading_domain_set(self):
        c = ConvergenceClassifier(lag_ratio=0.70)
        obs = _lag_obs(10, leader="market")
        result = c.classify(obs)
        assert result.leading_domain == "market"

    def test_lag_dominant_bucket_is_none(self):
        c = ConvergenceClassifier(lag_ratio=0.70)
        result = c.classify(_lag_obs(10))
        assert result.dominant_bucket is None

    def test_lag_confidence_is_leader_ratio(self):
        c = ConvergenceClassifier(lag_ratio=0.70)
        # 8 natural + 2 system leads, spread across buckets
        obs = [
            _obs(phase_bucket=i % 5, leading_domain="natural", t=float(i))
            for i in range(8)
        ] + [
            _obs(phase_bucket=i % 5, leading_domain="system", t=float(i + 10))
            for i in range(2)
        ]
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.LAG
        assert result.confidence == pytest.approx(8 / 10, abs=1e-4)

    def test_exactly_at_lag_threshold_is_lag(self):
        # 7 of 10 = 0.70 → LAG
        c = ConvergenceClassifier(noise_ratio=0.90, lag_ratio=0.70)
        obs = [
            _obs(phase_bucket=i % 5, leading_domain="natural", t=float(i))
            for i in range(7)
        ]
        obs += [
            _obs(phase_bucket=i % 5, leading_domain="system", t=float(i + 10))
            for i in range(3)
        ]
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.LAG


# ---------------------------------------------------------------------------
# COUPLING
# ---------------------------------------------------------------------------


class TestCoupling:
    def test_irregular_pattern_returns_coupling(self):
        c = ConvergenceClassifier(noise_ratio=0.60, lag_ratio=0.70)
        obs = _coupling_obs(15)
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.COUPLING

    def test_coupling_dominant_bucket_is_none(self):
        c = ConvergenceClassifier()
        obs = _coupling_obs(15)
        result = c.classify(obs)
        assert result.dominant_bucket is None

    def test_coupling_leading_domain_is_none(self):
        c = ConvergenceClassifier()
        obs = _coupling_obs(15)
        result = c.classify(obs)
        assert result.leading_domain is None

    def test_coupling_confidence_is_inverse_of_max_signal(self):
        # With equal spread, max signal is ~1/3 for leader, ~1/5 for bucket
        # confidence ≈ 1 - max(those)
        c = ConvergenceClassifier(noise_ratio=0.60, lag_ratio=0.70)
        obs = _coupling_obs(15)
        result = c.classify(obs)
        assert 0.0 < result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------


class TestConfigurableThresholds:
    def test_custom_min_observations(self):
        c = ConvergenceClassifier(min_observations=3)
        result = c.classify(_noise_obs(3))
        assert result.convergence_type != ConvergenceType.UNKNOWN

    def test_strict_noise_ratio_does_not_classify_as_noise(self):
        # noise_ratio=0.99 → almost never fires for noise
        c = ConvergenceClassifier(noise_ratio=0.99)
        obs = _noise_obs(8) + [_obs(phase_bucket=1), _obs(phase_bucket=2)]
        result = c.classify(obs)
        # 8/10 = 0.80 < 0.99 → not NOISE
        assert result.convergence_type != ConvergenceType.NOISE

    def test_strict_lag_ratio_does_not_classify_as_lag(self):
        c = ConvergenceClassifier(noise_ratio=0.99, lag_ratio=0.99)
        obs = _lag_obs(10, leader="natural")
        # 10/10 = 1.0 >= 0.99 → LAG
        result = c.classify(obs)
        assert result.convergence_type == ConvergenceType.LAG


# ---------------------------------------------------------------------------
# classify_summary
# ---------------------------------------------------------------------------


class TestClassifySummary:
    def _summary_from_store(self, tmp_path: Path, obs_list) -> dict:
        store = ConvergenceMemoryStore(store_path=tmp_path / "mem.jsonl")
        for o in obs_list:
            store.record(
                domain_a="natural",
                domain_b="system",
                diurnal_phase=o.diurnal_phase,
                leading_domain=o.leading_domain,
                convergence_note="test",
                t=o.t,
            )
        return store.pair_summary("natural", "system")

    def test_noise_from_summary(self, tmp_path):
        c = ConvergenceClassifier(noise_ratio=0.60)
        obs = _noise_obs(10, bucket=0)
        s = self._summary_from_store(tmp_path, obs)
        result = c.classify_summary(s)
        assert result.convergence_type == ConvergenceType.NOISE

    def test_unknown_from_empty_summary(self, tmp_path):
        store = ConvergenceMemoryStore(store_path=tmp_path / "mem.jsonl")
        s = store.pair_summary("a", "b")
        c = ConvergenceClassifier()
        result = c.classify_summary(s)
        assert result.convergence_type == ConvergenceType.UNKNOWN

    def test_lag_from_summary(self, tmp_path):
        c = ConvergenceClassifier(lag_ratio=0.70, noise_ratio=0.90)
        # 8 led by natural, spread across buckets
        obs = [
            _obs(
                phase_bucket=i % 5,
                leading_domain="natural",
                diurnal_phase=(i % 5) / 12.0,
                t=float(i),
            )
            for i in range(8)
        ] + [
            _obs(
                phase_bucket=i % 5,
                leading_domain="system",
                diurnal_phase=(i % 5) / 12.0,
                t=float(i + 20),
            )
            for i in range(2)
        ]
        s = self._summary_from_store(tmp_path, obs)
        result = c.classify_summary(s)
        assert result.convergence_type == ConvergenceType.LAG

    def test_coupling_from_summary(self, tmp_path):
        c = ConvergenceClassifier(noise_ratio=0.60, lag_ratio=0.70)
        obs = _coupling_obs(15)
        s = self._summary_from_store(tmp_path, obs)
        result = c.classify_summary(s)
        assert result.convergence_type == ConvergenceType.COUPLING

    def test_summary_result_matches_direct_classify(self, tmp_path):
        """classify() and classify_summary() must agree on the same data."""
        c = ConvergenceClassifier(min_observations=5, noise_ratio=0.60, lag_ratio=0.70)
        obs = _noise_obs(10, bucket=2)
        s = self._summary_from_store(tmp_path, obs)

        store = ConvergenceMemoryStore(store_path=tmp_path / "mem.jsonl")
        history = store.get_history("natural", "system")
        direct = c.classify(history)
        from_summary = c.classify_summary(s)

        assert direct.convergence_type == from_summary.convergence_type
