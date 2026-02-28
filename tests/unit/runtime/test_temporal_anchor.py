"""
Tests for rhythm_os.runtime.temporal_anchor

Invariants:
- All phases must be in [0.0, 1.0)
- Phases are deterministic for the same timestamp
- Each cycle has the correct period
- Domain hint selects correct dominant Hz
"""
from __future__ import annotations

import pytest
from rhythm_os.runtime.temporal_anchor import (
    compute_anchor,
    DIURNAL_PERIOD_S,
    SEMI_DIURNAL_PERIOD_S,
    LONG_WAVE_PERIOD_S,
    DIURNAL_HZ,
    SEMI_DIURNAL_HZ,
    LONG_WAVE_HZ,
)

# A known fixed timestamp (2024-01-15 12:00:00 UTC)
T_FIXED = 1705320000.0


# ------------------------------------------------------------------
# Phase range
# ------------------------------------------------------------------

class TestPhaseRange:
    def test_diurnal_phase_in_unit_interval(self):
        anchor = compute_anchor(T_FIXED)
        assert 0.0 <= anchor.diurnal_phase < 1.0

    def test_semi_diurnal_phase_in_unit_interval(self):
        anchor = compute_anchor(T_FIXED)
        assert 0.0 <= anchor.semi_diurnal_phase < 1.0

    def test_long_wave_phase_in_unit_interval(self):
        anchor = compute_anchor(T_FIXED)
        assert 0.0 <= anchor.long_wave_phase < 1.0

    def test_phases_at_zero_timestamp(self):
        anchor = compute_anchor(0.0)
        assert anchor.diurnal_phase == 0.0
        assert anchor.semi_diurnal_phase == 0.0
        assert anchor.long_wave_phase == 0.0


# ------------------------------------------------------------------
# Determinism
# ------------------------------------------------------------------

class TestDeterminism:
    def test_same_timestamp_same_phases(self):
        a = compute_anchor(T_FIXED, domain="system")
        b = compute_anchor(T_FIXED, domain="system")
        assert a.diurnal_phase == b.diurnal_phase
        assert a.semi_diurnal_phase == b.semi_diurnal_phase
        assert a.long_wave_phase == b.long_wave_phase

    def test_different_timestamps_different_phases(self):
        a = compute_anchor(T_FIXED)
        b = compute_anchor(T_FIXED + 3600.0)  # 1 hour later
        assert a.diurnal_phase != b.diurnal_phase


# ------------------------------------------------------------------
# Cycle periods
# ------------------------------------------------------------------

class TestCyclePeriods:
    def test_diurnal_full_cycle(self):
        """One full diurnal period should advance phase by exactly 1.0."""
        a = compute_anchor(T_FIXED)
        b = compute_anchor(T_FIXED + DIURNAL_PERIOD_S)
        assert abs(b.diurnal_phase - a.diurnal_phase) < 1e-9

    def test_semi_diurnal_half_cycle(self):
        """Half a semi-diurnal period should advance phase by ~0.5."""
        a = compute_anchor(T_FIXED)
        b = compute_anchor(T_FIXED + SEMI_DIURNAL_PERIOD_S / 2)
        diff = (b.semi_diurnal_phase - a.semi_diurnal_phase) % 1.0
        assert abs(diff - 0.5) < 1e-9

    def test_long_wave_quarter_cycle(self):
        """Quarter of a long-wave period should advance phase by ~0.25."""
        a = compute_anchor(T_FIXED)
        b = compute_anchor(T_FIXED + LONG_WAVE_PERIOD_S / 4)
        diff = (b.long_wave_phase - a.long_wave_phase) % 1.0
        assert abs(diff - 0.25) < 1e-9

    def test_semi_diurnal_completes_twice_per_diurnal(self):
        """Semi-diurnal completes 2 cycles for every 1 diurnal cycle."""
        a = compute_anchor(0.0)
        b = compute_anchor(DIURNAL_PERIOD_S)
        # Both should return to start (phase ≈ 0)
        assert abs(b.diurnal_phase - a.diurnal_phase) < 1e-9
        assert abs(b.semi_diurnal_phase - a.semi_diurnal_phase) < 1e-9


# ------------------------------------------------------------------
# Domain dominant frequency
# ------------------------------------------------------------------

class TestDomainDominantHz:
    def test_system_domain_uses_diurnal(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        assert anchor.dominant_hz == pytest.approx(DIURNAL_HZ)

    def test_natural_domain_uses_semi_diurnal(self):
        anchor = compute_anchor(T_FIXED, domain="natural")
        assert anchor.dominant_hz == pytest.approx(SEMI_DIURNAL_HZ)

    def test_market_domain_uses_diurnal(self):
        anchor = compute_anchor(T_FIXED, domain="market")
        assert anchor.dominant_hz == pytest.approx(DIURNAL_HZ)

    def test_narrative_domain_uses_long_wave(self):
        anchor = compute_anchor(T_FIXED, domain="narrative")
        assert anchor.dominant_hz == pytest.approx(LONG_WAVE_HZ)

    def test_unknown_domain_defaults_to_diurnal(self):
        anchor = compute_anchor(T_FIXED, domain="unknown_xyz")
        assert anchor.dominant_hz == pytest.approx(DIURNAL_HZ)

    def test_empty_domain_defaults_to_diurnal(self):
        anchor = compute_anchor(T_FIXED, domain="")
        assert anchor.dominant_hz == pytest.approx(DIURNAL_HZ)


# ------------------------------------------------------------------
# Immutability
# ------------------------------------------------------------------

class TestImmutability:
    def test_anchor_is_frozen(self):
        anchor = compute_anchor(T_FIXED)
        with pytest.raises(Exception):
            anchor.diurnal_phase = 0.99  # type: ignore[misc]
