"""
Tests for rhythm_os.domain.oracle.phase

Modules covered:
- _classify_pattern     (geometric phase classification)
- describe_alignment    (alignment descriptor construction)
- summarize_convergence (density summary)
- recognize_phase       (legacy stub)

Invariants:
- _classify_pattern returns "none" for low coherence
- _classify_pattern returns "near_lock" for small delta
- _classify_pattern returns "partial_alignment" for medium delta
- _classify_pattern returns "divergent" for large delta
- describe_alignment excludes waves outside the history window
- summarize_convergence returns "none" for empty descriptor list
- recognize_phase returns None (legacy stub)
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from rhythm_os.domain.oracle.phase import (
    _classify_pattern,
    describe_alignment,
    summarize_convergence,
    recognize_phase,
)
from rhythm_os.psr.domain_wave import DomainWave

_EXTRACTOR = {"method": "test"}


def _wave(
    *,
    t: float = 1000.0,
    domain: str = "test",
    channel: str = "ch",
    phase_diff: float = 0.0,
    coherence: Optional[float] = 0.8,
) -> DomainWave:
    return DomainWave(
        t=t,
        domain=domain,
        channel=channel,
        field_cycle="diurnal",
        phase_external=0.0,
        phase_field=0.0,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor=_EXTRACTOR,
    )


class TestClassifyPatternPhase:
    def test_low_coherence_returns_none(self):
        assert _classify_pattern(5.0, coherence=0.3) == "none"

    def test_high_coherence_near_zero_returns_near_lock(self):
        assert _classify_pattern(0.0, coherence=0.9) == "near_lock"

    def test_15_deg_is_near_lock(self):
        assert _classify_pattern(15.0, coherence=0.9) == "near_lock"

    def test_16_deg_is_partial_alignment(self):
        assert _classify_pattern(16.0, coherence=0.9) == "partial_alignment"

    def test_60_deg_is_partial_alignment(self):
        assert _classify_pattern(60.0, coherence=0.9) == "partial_alignment"

    def test_large_delta_is_divergent(self):
        assert _classify_pattern(90.0, coherence=0.9) == "divergent"

    def test_negative_large_delta_is_divergent(self):
        assert _classify_pattern(-90.0, coherence=0.9) == "divergent"

    def test_none_coherence_skips_noisy_check(self):
        result = _classify_pattern(5.0, coherence=None)
        assert result != "none"


class TestDescribeAlignmentPhase:
    def test_empty_waves_returns_empty(self):
        result = describe_alignment(t_ref=1000.0, domain_waves=[])
        assert result == []

    def test_wave_in_window_included(self):
        w = _wave(t=1000.0)
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert len(result) == 1

    def test_wave_out_of_window_excluded(self):
        w = _wave(t=0.0)
        result = describe_alignment(
            t_ref=10000.0, domain_waves=[w], history_window_sec=3600.0
        )
        assert result == []

    def test_descriptor_fields_correct(self):
        phase = math.pi / 6  # 30 degrees
        w = _wave(
            t=1000.0, domain="weather", channel="temp", phase_diff=phase, coherence=0.8
        )
        result = describe_alignment(
            t_ref=1000.0, domain_waves=[w], history_window_sec=3600.0
        )
        d = result[0]
        assert d.domain == "weather"
        assert d.channel == "temp"
        assert d.phase_diff_rad == pytest.approx(phase)
        assert d.phase_diff_deg == pytest.approx(30.0)


class TestSummarizeConvergencePhase:
    def test_empty_returns_none(self):
        result = summarize_convergence(t_ref=1000.0, descriptors=[])
        assert result.convergence == "none"
        assert result.within_count == 0
        assert result.mean_coherence is None

    def test_all_within_high(self):
        waves = [_wave(t=1000.0, phase_diff=0.1) for _ in range(10)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "high"

    def test_none_within_low(self):
        waves = [_wave(t=1000.0, phase_diff=math.pi) for _ in range(10)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "low"

    def test_moderate_convergence(self):
        near = [_wave(t=1000.0, phase_diff=0.1) for _ in range(5)]
        far = [_wave(t=1000.0, phase_diff=math.pi) for _ in range(5)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=near + far, history_window_sec=3600.0
        )
        result = summarize_convergence(
            t_ref=1000.0, descriptors=descriptors, within_deg=30.0
        )
        assert result.convergence == "moderate"

    def test_mean_coherence(self):
        waves = [_wave(t=1000.0, coherence=0.7) for _ in range(3)]
        descriptors = describe_alignment(
            t_ref=1000.0, domain_waves=waves, history_window_sec=3600.0
        )
        result = summarize_convergence(t_ref=1000.0, descriptors=descriptors)
        assert result.mean_coherence == pytest.approx(0.7)


class TestRecognizePhase:
    def test_returns_none(self):
        assert recognize_phase() is None

    def test_accepts_inputs_kwarg(self):
        assert recognize_phase(inputs={"x": 1}) is None
