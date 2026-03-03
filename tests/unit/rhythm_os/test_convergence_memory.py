"""
Tests for rhythm_os.domain.convergence.memory_store

Modules covered:
- phase_to_bucket
- pair_key
- ConvergenceObservation (to_dict / from_dict)
- ConvergenceMemoryStore.record
- ConvergenceMemoryStore.get_history
- ConvergenceMemoryStore.pair_summary
- ConvergenceMemoryStore.all_pairs

Invariants:
- phase_to_bucket maps [0,1) uniformly into [0, N_BUCKETS)
- pair_key is symmetric: pair_key(a,b) == pair_key(b,a)
- ConvergenceObservation round-trips through to_dict/from_dict
- record() persists to JSONL and returns the observation
- get_history() filters by domain pair
- get_history() optionally filters by phase_bucket
- get_history() returns most-recent first
- get_history() respects max_records
- pair_summary() returns correct counts for bucket/leader/total
- pair_summary() returns zeroed structure for unknown pair
- all_pairs() returns unique sorted pair keys
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rhythm_os.domain.convergence.memory_store import (
    N_BUCKETS,
    ConvergenceMemoryStore,
    ConvergenceObservation,
    pair_key,
    phase_to_bucket,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> ConvergenceMemoryStore:
    return ConvergenceMemoryStore(store_path=tmp_path / "memory.jsonl")


def _record(
    store: ConvergenceMemoryStore,
    *,
    domain_a: str = "natural",
    domain_b: str = "system",
    diurnal_phase: float = 0.0,
    leading_domain: str = "natural",
    convergence_note: str = "weak:system",
    t: float = 1000.0,
) -> ConvergenceObservation:
    return store.record(
        domain_a=domain_a,
        domain_b=domain_b,
        diurnal_phase=diurnal_phase,
        leading_domain=leading_domain,
        convergence_note=convergence_note,
        t=t,
    )


# ---------------------------------------------------------------------------
# phase_to_bucket
# ---------------------------------------------------------------------------


class TestPhaseToBucket:
    def test_zero_phase_is_bucket_zero(self):
        assert phase_to_bucket(0.0) == 0

    def test_full_cycle_wraps_to_zero(self):
        assert phase_to_bucket(1.0) == 0

    def test_midpoint_is_half_buckets(self):
        assert phase_to_bucket(0.5) == N_BUCKETS // 2

    def test_all_phases_in_range(self):
        for i in range(100):
            p = i / 100.0
            b = phase_to_bucket(p)
            assert 0 <= b < N_BUCKETS

    def test_consecutive_buckets_span_uniformly(self):
        # Use bucket midpoints to avoid floating-point boundary ambiguity.
        # Each bucket covers [i/N, (i+1)/N); midpoint is (i+0.5)/N.
        for i in range(N_BUCKETS):
            midpoint = (i + 0.5) / N_BUCKETS
            assert phase_to_bucket(midpoint) == i

    def test_custom_n_buckets(self):
        assert phase_to_bucket(0.5, n_buckets=4) == 2
        assert phase_to_bucket(0.25, n_buckets=4) == 1


# ---------------------------------------------------------------------------
# pair_key
# ---------------------------------------------------------------------------


class TestPairKey:
    def test_symmetric(self):
        assert pair_key("natural", "system") == pair_key("system", "natural")

    def test_alphabetical_order(self):
        assert pair_key("zebra", "apple") == "apple+zebra"

    def test_same_domain(self):
        # Unusual but shouldn't crash
        assert pair_key("a", "a") == "a+a"

    def test_whitespace_stripped(self):
        assert pair_key("  natural  ", "system") == pair_key("natural", "system")


# ---------------------------------------------------------------------------
# ConvergenceObservation round-trip
# ---------------------------------------------------------------------------


class TestConvergenceObservationRoundTrip:
    def test_round_trip_preserves_all_fields(self, tmp_path):
        store = _store(tmp_path)
        obs = _record(store)
        d = obs.to_dict()
        obs2 = ConvergenceObservation.from_dict(d)
        assert obs2.obs_id == obs.obs_id
        assert obs2.t == pytest.approx(obs.t)
        assert obs2.domain_pair == obs.domain_pair
        assert obs2.phase_bucket == obs.phase_bucket
        assert obs2.diurnal_phase == pytest.approx(obs.diurnal_phase)
        assert obs2.leading_domain == obs.leading_domain
        assert obs2.convergence_note == obs.convergence_note


# ---------------------------------------------------------------------------
# ConvergenceMemoryStore.record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_returns_observation(self, tmp_path):
        store = _store(tmp_path)
        obs = _record(store)
        assert isinstance(obs, ConvergenceObservation)

    def test_pair_key_is_sorted(self, tmp_path):
        store = _store(tmp_path)
        obs = _record(store, domain_a="system", domain_b="natural")
        assert obs.domain_pair == "natural+system"

    def test_phase_bucket_matches_diurnal_phase(self, tmp_path):
        store = _store(tmp_path)
        obs = _record(store, diurnal_phase=0.5)
        assert obs.phase_bucket == phase_to_bucket(0.5)

    def test_unique_obs_ids(self, tmp_path):
        store = _store(tmp_path)
        ids = {_record(store, t=float(i)).obs_id for i in range(10)}
        assert len(ids) == 10

    def test_persists_to_file(self, tmp_path):
        path = tmp_path / "memory.jsonl"
        store = ConvergenceMemoryStore(store_path=path)
        _record(store)
        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_multiple_records_accumulate(self, tmp_path):
        path = tmp_path / "memory.jsonl"
        store = ConvergenceMemoryStore(store_path=path)
        for i in range(5):
            _record(store, t=float(i))
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_explicit_t_used(self, tmp_path):
        store = _store(tmp_path)
        obs = _record(store, t=99999.0)
        assert obs.t == pytest.approx(99999.0)


# ---------------------------------------------------------------------------
# ConvergenceMemoryStore.get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_empty_store_returns_empty(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_history("natural", "system") == []

    def test_returns_matching_pair(self, tmp_path):
        store = _store(tmp_path)
        _record(store, domain_a="natural", domain_b="system", t=1.0)
        history = store.get_history("natural", "system")
        assert len(history) == 1

    def test_different_pair_not_returned(self, tmp_path):
        store = _store(tmp_path)
        _record(store, domain_a="natural", domain_b="system", t=1.0)
        _record(store, domain_a="market", domain_b="system", t=2.0)
        history = store.get_history("natural", "system")
        assert len(history) == 1
        assert history[0].domain_pair == "natural+system"

    def test_pair_lookup_is_symmetric(self, tmp_path):
        store = _store(tmp_path)
        _record(store, domain_a="system", domain_b="natural", t=1.0)
        # Look up with reversed order
        history = store.get_history("natural", "system")
        assert len(history) == 1

    def test_filter_by_phase_bucket(self, tmp_path):
        store = _store(tmp_path)
        _record(store, diurnal_phase=0.0, t=1.0)  # bucket 0
        _record(store, diurnal_phase=0.5, t=2.0)  # bucket 6
        bucket0 = store.get_history("natural", "system", phase_bucket=0)
        assert len(bucket0) == 1
        assert bucket0[0].phase_bucket == 0

    def test_most_recent_first(self, tmp_path):
        store = _store(tmp_path)
        for t in [100.0, 200.0, 300.0]:
            _record(store, t=t)
        history = store.get_history("natural", "system")
        times = [o.t for o in history]
        assert times == sorted(times, reverse=True)

    def test_max_records_respected(self, tmp_path):
        store = _store(tmp_path)
        for i in range(10):
            _record(store, t=float(i))
        history = store.get_history("natural", "system", max_records=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# ConvergenceMemoryStore.pair_summary
# ---------------------------------------------------------------------------


class TestPairSummary:
    def test_unknown_pair_returns_zeroed(self, tmp_path):
        store = _store(tmp_path)
        s = store.pair_summary("x", "y")
        assert s["total_count"] == 0
        assert s["first_seen"] is None
        assert s["last_seen"] is None
        assert s["dominant_bucket"] is None

    def test_total_count_correct(self, tmp_path):
        store = _store(tmp_path)
        for i in range(5):
            _record(store, t=float(i))
        s = store.pair_summary("natural", "system")
        assert s["total_count"] == 5

    def test_bucket_counts_correct(self, tmp_path):
        store = _store(tmp_path)
        _record(store, diurnal_phase=0.0, t=1.0)  # bucket 0
        _record(store, diurnal_phase=0.0, t=2.0)  # bucket 0
        _record(store, diurnal_phase=0.5, t=3.0)  # bucket 6
        s = store.pair_summary("natural", "system")
        assert s["bucket_counts"][0] == 2
        assert s["bucket_counts"][6] == 1

    def test_leading_counts_correct(self, tmp_path):
        store = _store(tmp_path)
        _record(store, leading_domain="natural", t=1.0)
        _record(store, leading_domain="natural", t=2.0)
        _record(store, leading_domain="system", t=3.0)
        s = store.pair_summary("natural", "system")
        assert s["leading_counts"]["natural"] == 2
        assert s["leading_counts"]["system"] == 1

    def test_dominant_bucket_is_most_frequent(self, tmp_path):
        store = _store(tmp_path)
        for _ in range(4):
            _record(store, diurnal_phase=0.0, t=1.0)  # bucket 0
        _record(store, diurnal_phase=0.5, t=2.0)  # bucket 6
        s = store.pair_summary("natural", "system")
        assert s["dominant_bucket"] == 0

    def test_first_and_last_seen(self, tmp_path):
        store = _store(tmp_path)
        _record(store, t=100.0)
        _record(store, t=500.0)
        _record(store, t=300.0)
        s = store.pair_summary("natural", "system")
        assert s["first_seen"] == pytest.approx(100.0)
        assert s["last_seen"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# ConvergenceMemoryStore.all_pairs
# ---------------------------------------------------------------------------


class TestAllPairs:
    def test_empty_store(self, tmp_path):
        store = _store(tmp_path)
        assert store.all_pairs() == []

    def test_single_pair(self, tmp_path):
        store = _store(tmp_path)
        _record(store)
        assert store.all_pairs() == ["natural+system"]

    def test_multiple_pairs_sorted(self, tmp_path):
        store = _store(tmp_path)
        _record(store, domain_a="natural", domain_b="system", t=1.0)
        _record(store, domain_a="market", domain_b="natural", t=2.0)
        _record(store, domain_a="natural", domain_b="system", t=3.0)  # duplicate pair
        pairs = store.all_pairs()
        assert pairs == sorted(pairs)
        assert len(pairs) == 2

    def test_pairs_are_canonical(self, tmp_path):
        store = _store(tmp_path)
        _record(store, domain_a="system", domain_b="natural", t=1.0)
        _record(store, domain_a="natural", domain_b="system", t=2.0)
        # Both produce the same pair key → only one unique pair
        assert store.all_pairs() == ["natural+system"]
