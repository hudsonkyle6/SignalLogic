"""
Tests for rhythm_os.domain.oracle.oracle

Modules covered:
- _classify_pattern  (geometric pattern classification)
- describe_alignment (alignment descriptor construction from DomainWaves)
- summarize_convergence (spatial density summary)
- Oracle            (class adapter)

Invariants:
- _classify_pattern returns one of the Pattern literals
- describe_alignment skips waves outside the history window
- summarize_convergence handles empty descriptor list
- Oracle.describe / Oracle.summarize_convergence delegate to pure functions
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from rhythm_os.domain.oracle.oracle import (
    _classify_pattern,
    describe_alignment,
    summarize_convergence,
    ConvergenceSummary,
    Oracle,
)
from rhythm_os.psr.domain_wave import DomainWave

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXTRACTOR = {"method": "test"}


def _wave(
    *,
    t: float = 1000.0,
    domain: str = "test",
    channel: str = "ch",
    phase_diff: float = 0.0,
    coherence: Optional[float] = 0.8,
    field_cycle: str = "diurnal",
) -> DomainWave:
    return DomainWave(
        t=t,
        domain=domain,
        channel=channel,
        field_cycle=field_cycle,
        phase_external=0.0,
        phase_field=0.0,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor=_EXTRACTOR,
    )


# ---------------------------------------------------------------------------
# _classify_pattern
# ---------------------------------------------------------------------------


class TestClassifyPattern:
    def test_low_coherence_returns_noisy(self):
        result = _classify_pattern(5.0, coherence=0.3)
        assert result == "noisy"

    def test_coherence_exactly_half_is_noisy(self):
        # coherence < 0.5 → noisy
        result = _classify_pattern(5.0, coherence=0.499)
        assert result == "noisy"

    def test_coherence_none_skips_noisy_check(self):
        # coherence is None → should not return noisy
        result = _classify_pattern(5.0, coherence=None)
        assert result != "noisy"

    def test_near_zero_delta_is_near_lock(self):
        result = _classify_pattern(0.0, coherence=0.9)
        assert result == "near_lock"

    def test_delta_15_deg_is_near_lock(self):
        result = _classify_pattern(15.0, coherence=0.9)
        assert result == "near_lock"

    def test_delta_16_deg_is_partial_alignment(self):
        result = _classify_pattern(16.0, coherence=0.9)
        assert result == "partial_alignment"

    def test_delta_60_deg_is_partial_alignment(self):
        result = _classify_pattern(60.0, coherence=0.9)
        assert result == "partial_alignment"

    def test_delta_positive_large_is_phase_leading(self):
        result = _classify_pattern(90.0, coherence=0.9)
        assert result == "phase_leading"

    def test_delta_negative_large_is_phase_lagging(self):
        result = _classify_pattern(-90.0, coherence=0.9)
        assert result == "phase_lagging"

    def test_returns_one_of_valid_patterns(self):
        valid = {
            "noisy",
            "near_lock",
            "partial_alignment",
            "phase_lagging",
            "phase_leading",
        }
        for delta in [-180, -90, -60, -15, 0, 15, 60, 90, 180]:
            for coh in [None, 0.0, 0.4, 0.5, 0.9, 1.0]:
                result = _classify_pattern(float(delta), coherence=coh)
                assert result in valid


# ---------------------------------------------------------------------------
# describe_alignment
# ---------------------------------------------------------------------------


class TestDescribeAlignment:
    def test_empty_waves_returns_empty(self):
        result = describe_alignment(
            t_ref=1000.0,
            domain_waves=[],
            history_window_sec=3600.0,
        )
        assert result == []

    def test_wave_within_window_is_included(self):
        w = _wave(t=1000.0, phase_diff=0.1)
        result = describe_alignment(
            t_ref=1000.0,
            domain_waves=[w],
            history_window_sec=3600.0,
        )
        assert len(result) == 1

    def test_wave_outside_window_is_excluded(self):
        w = _wave(t=0.0, phase_diff=0.1)
        result = describe_alignment(
            t_ref=10000.0,
            domain_waves=[w],
            history_window_sec=3600.0,
        )
        assert result == []

    def test_descriptor_has_correct_fields(self):
        w = _wave(
            t=1000.0, domain="weather", channel="temp", phase_diff=0.2, coherence=0.7
        )
        result = describe_alignment(
            t_ref=1000.0,
            domain_waves=[w],
            history_window_sec=3600.0,
        )
        assert len(result) == 1
        d = result[0]
        assert d.t == 1000.0
        assert d.domain == "weather"
        assert d.channel == "temp"
        assert d.coherence_ext == pytest.approx(0.7)

    def test_phase_diff_rad_matches_wave(self):
        phase = 1.5
        w = _wave(t=1000.0, phase_diff=phase)
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert result[0].phase_diff_rad == pytest.approx(phase)

    def test_phase_diff_deg_is_degrees(self):
        phase = math.pi / 4  # 45 degrees
        w = _wave(t=1000.0, phase_diff=phase)
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert result[0].phase_diff_deg == pytest.approx(45.0)

    def test_none_coherence_passed_through(self):
        w = _wave(t=1000.0, coherence=None)
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert result[0].coherence_ext is None

    def test_multiple_waves_all_in_window(self):
        waves = [_wave(t=1000.0 + i, phase_diff=0.1 * i) for i in range(5)]
        result = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        assert len(result) == 5

    def test_field_cycle_taken_from_wave(self):
        w = _wave(t=1000.0, field_cycle="semi_diurnal")
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert result[0].field_cycle == "semi_diurnal"


# ---------------------------------------------------------------------------
# summarize_convergence
# ---------------------------------------------------------------------------


class TestSummarizeConvergence:
    def test_empty_descriptors_returns_none_convergence(self):
        result = summarize_convergence(t_ref=1000.0, descriptors=[])
        assert isinstance(result, ConvergenceSummary)
        assert result.convergence == "none"
        assert result.active == 0
        assert result.within_count == 0
        assert result.mean_coherence is None

    def test_all_within_window_high_convergence(self):
        waves = [_wave(t=1000.0, phase_diff=0.1) for _ in range(10)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "high"

    def test_none_within_window_low_convergence(self):
        # All waves have large phase diff > 30 deg
        waves = [_wave(t=1000.0, phase_diff=math.pi) for _ in range(10)]  # 180 deg
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "low"
        assert result.within_count == 0

    def test_moderate_convergence(self):
        # About 50% within threshold
        near = [_wave(t=1000.0, phase_diff=0.1) for _ in range(5)]
        far = [_wave(t=1000.0, phase_diff=math.pi) for _ in range(5)]
        all_waves = near + far
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=all_waves, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "moderate"

    def test_mean_coherence_computed(self):
        waves = [_wave(t=1000.0, phase_diff=0.1, coherence=0.8) for _ in range(3)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(t_ref=1000.0, descriptors=descriptors)
        assert result.mean_coherence == pytest.approx(0.8)

    def test_none_coherences_excluded_from_mean(self):
        waves = [_wave(t=1000.0, coherence=None) for _ in range(3)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(t_ref=1000.0, descriptors=descriptors)
        assert result.mean_coherence is None

    def test_summary_has_correct_t(self):
        result = summarize_convergence(t_ref=9999.0, descriptors=[])
        assert result.t == 9999.0

    def test_within_count_correct(self):
        near = [_wave(t=1000.0, phase_diff=0.1) for _ in range(7)]  # 7 within 30 deg
        far = [_wave(t=1000.0, phase_diff=math.pi) for _ in range(3)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=near + far, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.within_count == 7
        assert result.active == 10


# ---------------------------------------------------------------------------
# Oracle class
# ---------------------------------------------------------------------------


class TestOracle:
    def test_describe_returns_list(self):
        oracle = Oracle(history_window_hours=1.0)
        waves = [_wave(t=1000.0)]
        result = oracle.describe(t_now=1000.0, domain_waves=waves)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_describe_ignores_field_waves(self):
        oracle = Oracle(history_window_hours=1.0)
        waves = [_wave(t=1000.0)]
        result_without = oracle.describe(t_now=1000.0, domain_waves=waves)
        result_with = oracle.describe(
            t_now=1000.0, domain_waves=waves, field_waves=["ignored"]
        )
        # field_waves is ignored — results should be identical
        assert len(result_without) == len(result_with)

    def test_history_window_respected(self):
        oracle = Oracle(history_window_hours=1.0)
        w_in = _wave(t=1000.0)
        w_out = _wave(t=0.0)  # 1000 sec before t_now, well within 1h
        result = oracle.describe(t_now=1000.0, domain_waves=[w_in, w_out])
        assert len(result) == 2  # both within 3600s of t=1000

    def test_summarize_convergence_delegates(self):
        oracle = Oracle()
        waves = [_wave(t=1000.0)]
        descriptors = oracle.describe(t_now=1000.0, domain_waves=waves)
        summary = oracle.summarize_convergence(t_ref=1000.0, descriptors=descriptors)
        assert isinstance(summary, ConvergenceSummary)

    def test_default_history_window_is_24h(self):
        oracle = Oracle()
        assert oracle.history_window_sec == pytest.approx(24.0 * 3600.0)
