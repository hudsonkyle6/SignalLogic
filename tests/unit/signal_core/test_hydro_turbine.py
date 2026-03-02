"""
Tests for signal_core.core.hydro_turbine

Invariants:
- Phase circular distance is always in [0, 0.5]
- Convergence is domain-aware (same-domain packets do not self-converge)
- Isolated packets produce empty aligned_domains
- Cross-domain packets within window produce non-empty aligned_domains
- Convergence note format is consistent
"""

from __future__ import annotations

import pytest
from signal_core.core.hydro_turbine import (
    _circular_distance,
    _assess_convergence,
    CONVERGENCE_WINDOW,
)
from rhythm_os.runtime.temporal_anchor import compute_anchor

T_FIXED = 1705320000.0


# ------------------------------------------------------------------
# Phase geometry
# ------------------------------------------------------------------


class TestCircularDistance:
    def test_identical_phases(self):
        assert _circular_distance(0.5, 0.5) == pytest.approx(0.0)

    def test_opposite_phases(self):
        assert _circular_distance(0.0, 0.5) == pytest.approx(0.5)

    def test_wraps_correctly(self):
        # distance from 0.95 to 0.05 should be 0.10, not 0.90
        assert _circular_distance(0.95, 0.05) == pytest.approx(0.10)

    def test_symmetric(self):
        a, b = 0.3, 0.7
        assert _circular_distance(a, b) == pytest.approx(_circular_distance(b, a))

    def test_result_always_in_zero_to_half(self):
        for i in range(20):
            a = i / 20
            for j in range(20):
                b = j / 20
                d = _circular_distance(a, b)
                assert 0.0 <= d <= 0.5


# ------------------------------------------------------------------
# Convergence assessment
# ------------------------------------------------------------------


def _rec(domain: str, diurnal_phase: float) -> dict:
    return {"domain": domain, "diurnal_phase": diurnal_phase}


class TestAssessConvergence:
    def test_no_history_returns_no_history(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        domains, note = _assess_convergence(anchor, "system", [])
        assert domains == []
        assert note == "no_history"

    def test_no_nearby_foreign_domain_isolated(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        history = [_rec("natural", (anchor.diurnal_phase + 0.4) % 1.0)]
        domains, note = _assess_convergence(anchor, "system", history)
        assert domains == []
        assert note == "isolated"

    def test_same_domain_excluded_from_convergence(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        # A system record at exact same phase — should not count (same domain)
        history = [_rec("system", anchor.diurnal_phase)]
        domains, note = _assess_convergence(anchor, "system", history)
        assert "system" not in domains
        assert note == "isolated"

    def test_foreign_domain_within_window_converges(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        nearby = (anchor.diurnal_phase + CONVERGENCE_WINDOW * 0.5) % 1.0
        history = [_rec("natural", nearby)]
        domains, note = _assess_convergence(anchor, "system", history)
        assert "natural" in domains
        assert "weak" in note or "convergence" in note

    def test_two_foreign_domains_strong_convergence(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        nearby = (anchor.diurnal_phase + CONVERGENCE_WINDOW * 0.5) % 1.0
        history = [
            _rec("natural", nearby),
            _rec("cyber", nearby),
        ]
        domains, note = _assess_convergence(anchor, "system", history)
        assert "natural" in domains
        assert "cyber" in domains
        assert "convergence" in note

    def test_most_recent_per_domain_used(self):
        """Only the first occurrence per domain in history should be used."""
        anchor = compute_anchor(T_FIXED, domain="system")
        nearby = (anchor.diurnal_phase + CONVERGENCE_WINDOW * 0.5) % 1.0
        far = (anchor.diurnal_phase + 0.4) % 1.0
        # First natural record is nearby, second is far — first should win
        history = [
            _rec("natural", nearby),
            _rec("natural", far),
        ]
        domains, note = _assess_convergence(anchor, "system", history)
        assert "natural" in domains

    def test_domain_just_outside_window_not_converged(self):
        anchor = compute_anchor(T_FIXED, domain="system")
        just_outside = (anchor.diurnal_phase + CONVERGENCE_WINDOW + 0.01) % 1.0
        history = [_rec("natural", just_outside)]
        domains, note = _assess_convergence(anchor, "system", history)
        assert domains == []
        assert note == "isolated"
