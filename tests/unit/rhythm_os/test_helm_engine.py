"""
Tests for rhythm_os.domain.helm.engine

Covers all four states, antifragile overrides, edge cases, and the
HelmResult API.
"""

from __future__ import annotations

import types
from typing import Any

import pytest

from rhythm_os.domain.helm.engine import (
    HELM_GUIDANCE,
    HELM_STYLES,
    HelmResult,
    compute_helm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cr(
    *,
    drained: int = 100,
    committed: int = 80,
    quarantined: int = 0,
    strong: int = 0,
    event_count: int = 0,
    events: list | None = None,
) -> Any:
    """Build a minimal CycleResult-like namespace for testing."""
    cs = {
        "strong_events": strong,
        "convergence_event_count": event_count,
        "convergence_events": events or [],
    }
    return types.SimpleNamespace(
        packets_drained=drained,
        committed=committed,
        spillway_quarantined=quarantined,
        convergence_summary=cs,
    )


# ---------------------------------------------------------------------------
# HelmResult API
# ---------------------------------------------------------------------------


class TestHelmResultAPI:
    def test_frozen(self):
        h = HelmResult(state="ACT", rationale="test", ts=1.0)
        with pytest.raises((TypeError, AttributeError)):
            h.state = "WAIT"  # type: ignore[misc]

    def test_guidance_property(self):
        for state, expected in HELM_GUIDANCE.items():
            h = HelmResult(state=state, rationale="x", ts=1.0)
            assert h.guidance == expected

    def test_style_property(self):
        for state, expected in HELM_STYLES.items():
            h = HelmResult(state=state, rationale="x", ts=1.0)
            assert h.style == expected

    def test_guidance_unknown_state(self):
        h = HelmResult(state="UNKNOWN", rationale="x", ts=1.0)
        assert h.guidance == ""

    def test_style_unknown_state(self):
        h = HelmResult(state="UNKNOWN", rationale="x", ts=1.0)
        assert h.style == ("dim", "·")

    def test_as_dict_has_all_fields(self):
        h = HelmResult(
            state="ACT", rationale="r", ts=1.0,
            admission_rate=0.85, anomaly_rate=0.01,
            strong_events=0, event_count=0,
            brittleness=0.2, strain=0.3,
        )
        d = h.as_dict()
        assert d["state"] == "ACT"
        assert d["admission_rate"] == pytest.approx(0.85)
        assert d["brittleness"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# None input
# ---------------------------------------------------------------------------


class TestNoneInput:
    def test_returns_prepare(self):
        h = compute_helm(None)
        assert h.state == "PREPARE"

    def test_rationale_mentions_baseline(self):
        h = compute_helm(None)
        assert "baseline" in h.rationale.lower() or "cycle" in h.rationale.lower()

    def test_ts_is_float(self):
        h = compute_helm(None)
        assert isinstance(h.ts, float)


# ---------------------------------------------------------------------------
# Layer 1: Antifragile overrides
# ---------------------------------------------------------------------------


class TestAntifragileOverrides:
    def test_high_brittleness_forces_wait(self):
        cr = _cr(committed=90, drained=100)
        h = compute_helm(cr, antifragile={"brittleness_index": 0.75})
        assert h.state == "WAIT"
        assert "brittleness" in h.rationale

    def test_brittleness_at_threshold_is_wait(self):
        cr = _cr(committed=90, drained=100)
        h = compute_helm(cr, antifragile={"brittleness_index": 0.71})
        assert h.state == "WAIT"

    def test_brittleness_below_threshold_passes_through(self):
        # 0.69 should NOT trigger the brittleness override
        cr = _cr(committed=90, drained=100)
        h = compute_helm(cr, antifragile={"brittleness_index": 0.69})
        assert h.state != "WAIT" or "brittleness" not in h.rationale

    def test_high_strain_forces_wait(self):
        cr = _cr(committed=90, drained=100)
        h = compute_helm(cr, antifragile={"strain_index": 0.85})
        assert h.state == "WAIT"
        assert "strain" in h.rationale

    def test_strain_below_threshold_no_override(self):
        cr = _cr(committed=90, drained=100)
        h = compute_helm(cr, antifragile={"strain_index": 0.79})
        # Should not force WAIT purely due to strain
        assert h.state in {"ACT", "PUSH", "PREPARE"}

    def test_drift_floor_prevents_push(self):
        # High admission + no anomalies would normally be PUSH, but
        # high drift should floor it at PREPARE.
        cr = _cr(committed=92, drained=100, quarantined=0)
        h = compute_helm(cr, antifragile={"drift_index": 0.65})
        assert h.state == "PREPARE"
        assert "drift" in h.rationale

    def test_drift_below_threshold_allows_push(self):
        cr = _cr(committed=92, drained=100, quarantined=0)
        h = compute_helm(cr, antifragile={"drift_index": 0.59})
        assert h.state == "PUSH"

    def test_no_antifragile_no_override(self):
        # Baseline healthy cycle — no antifragile kwarg → ACT or PUSH
        cr = _cr(committed=85, drained=100)
        h = compute_helm(cr)
        assert h.state in {"ACT", "PUSH"}


# ---------------------------------------------------------------------------
# Layer 2: Routing stress
# ---------------------------------------------------------------------------


class TestRoutingStress:
    def test_high_anomaly_rate_wait(self):
        cr = _cr(committed=80, drained=100, quarantined=15)
        h = compute_helm(cr)
        assert h.state == "WAIT"
        assert "anomal" in h.rationale.lower()

    def test_anomaly_exactly_at_threshold(self):
        # 10 quarantined / 100 drained = exactly 0.10 — not > 0.10 so NO override
        cr = _cr(committed=80, drained=100, quarantined=10)
        h = compute_helm(cr)
        assert h.state != "WAIT" or "anomal" not in h.rationale.lower()

    def test_low_admission_wait(self):
        cr = _cr(committed=45, drained=100)
        h = compute_helm(cr)
        assert h.state == "WAIT"
        assert "admission" in h.rationale.lower()

    def test_admission_exactly_at_threshold(self):
        # 50 / 100 = 0.50 — not < 0.50 so no routing stress WAIT
        cr = _cr(committed=50, drained=100)
        h = compute_helm(cr)
        assert h.state not in {"WAIT"} or "admission" not in h.rationale


# ---------------------------------------------------------------------------
# Layer 3: Convergence pressure
# ---------------------------------------------------------------------------


class TestConvergencePressure:
    def test_strong_convergence_wait(self):
        ev = {"strength": "strong", "domains": ["market", "natural", "system"]}
        cr = _cr(committed=80, drained=100, strong=1, event_count=1, events=[ev])
        h = compute_helm(cr)
        assert h.state == "WAIT"

    def test_strong_convergence_rationale_includes_domains(self):
        ev = {"strength": "strong", "domains": ["market", "natural"]}
        cr = _cr(committed=80, drained=100, strong=1, event_count=1, events=[ev])
        h = compute_helm(cr)
        assert "market" in h.rationale or "natural" in h.rationale

    def test_strong_convergence_no_event_detail(self):
        # strong_events > 0 but convergence_events list is empty
        cr = _cr(committed=80, drained=100, strong=1, event_count=1, events=[])
        h = compute_helm(cr)
        assert h.state == "WAIT"

    def test_weak_convergence_prepare(self):
        ev = {"strength": "weak", "domains": ["market", "cyber"]}
        cr = _cr(committed=80, drained=100, strong=0, event_count=1, events=[ev])
        h = compute_helm(cr)
        assert h.state == "PREPARE"

    def test_weak_convergence_rationale_includes_domains(self):
        ev = {"strength": "weak", "domains": ["cyber", "system"]}
        cr = _cr(committed=80, drained=100, strong=0, event_count=1, events=[ev])
        h = compute_helm(cr)
        assert "cyber" in h.rationale or "system" in h.rationale

    def test_weak_convergence_no_event_detail(self):
        cr = _cr(committed=80, drained=100, strong=0, event_count=1, events=[])
        h = compute_helm(cr)
        assert h.state == "PREPARE"


# ---------------------------------------------------------------------------
# Layer 4/5: Clean-window and defaults
# ---------------------------------------------------------------------------


class TestCleanWindow:
    def test_high_admission_no_anomalies_push(self):
        cr = _cr(committed=90, drained=100, quarantined=0)
        h = compute_helm(cr)
        assert h.state == "PUSH"

    def test_high_admission_with_anomalies_not_push(self):
        # 11 quarantined → anom_rate 0.11 > 0.10 → WAIT
        cr = _cr(committed=90, drained=100, quarantined=11)
        h = compute_helm(cr)
        assert h.state == "WAIT"

    def test_nominal_admission_act(self):
        cr = _cr(committed=75, drained=100, quarantined=0)
        h = compute_helm(cr)
        assert h.state == "ACT"

    def test_act_rationale_includes_pct(self):
        cr = _cr(committed=75, drained=100, quarantined=0)
        h = compute_helm(cr)
        assert "75%" in h.rationale

    def test_push_rationale_includes_pct(self):
        cr = _cr(committed=90, drained=100, quarantined=0)
        h = compute_helm(cr)
        assert "90%" in h.rationale


# ---------------------------------------------------------------------------
# Metrics stored on result
# ---------------------------------------------------------------------------


class TestMetricsOnResult:
    def test_admission_rate_stored(self):
        cr = _cr(committed=75, drained=100)
        h = compute_helm(cr)
        assert h.admission_rate == pytest.approx(0.75)

    def test_anomaly_rate_stored(self):
        cr = _cr(committed=75, drained=100, quarantined=5)
        h = compute_helm(cr)
        assert h.anomaly_rate == pytest.approx(0.05)

    def test_strong_events_stored(self):
        ev = {"strength": "strong", "domains": ["market", "natural"]}
        cr = _cr(committed=75, drained=100, strong=1, event_count=1, events=[ev])
        h = compute_helm(cr)
        assert h.strong_events == 1

    def test_brittleness_stored(self):
        cr = _cr(committed=75, drained=100)
        h = compute_helm(cr, antifragile={"brittleness_index": 0.4})
        assert h.brittleness == pytest.approx(0.4)

    def test_strain_stored(self):
        cr = _cr(committed=75, drained=100)
        h = compute_helm(cr, antifragile={"strain_index": 0.3})
        assert h.strain == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_packets_drained(self):
        cr = types.SimpleNamespace(
            packets_drained=0,
            committed=0,
            spillway_quarantined=0,
            convergence_summary={},
        )
        # Should not raise; drained treated as 1 internally
        h = compute_helm(cr)
        assert h.state in {"WAIT", "PREPARE", "ACT", "PUSH"}

    def test_missing_convergence_summary(self):
        cr = types.SimpleNamespace(
            packets_drained=100,
            committed=80,
            spillway_quarantined=0,
            convergence_summary=None,
        )
        h = compute_helm(cr)
        assert h.state in {"ACT", "PUSH"}

    def test_all_states_are_valid(self):
        valid = {"WAIT", "PREPARE", "ACT", "PUSH"}
        scenarios = [
            _cr(committed=45, drained=100),                                  # WAIT low adm
            _cr(committed=80, drained=100, quarantined=15),                  # WAIT anomaly
            _cr(committed=80, drained=100, strong=1, event_count=1,
                events=[{"strength": "strong", "domains": ["a", "b"]}]),     # WAIT strong
            _cr(committed=80, drained=100, event_count=1,
                events=[{"strength": "weak", "domains": ["a"]}]),            # PREPARE weak
            _cr(committed=75, drained=100),                                  # ACT nominal
            _cr(committed=92, drained=100),                                  # PUSH clean
        ]
        for cr in scenarios:
            assert compute_helm(cr).state in valid
