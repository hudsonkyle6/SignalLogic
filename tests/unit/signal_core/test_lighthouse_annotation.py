"""
Tests for signal_core.core.lighthouse — annotate_packet()

Invariants:
- annotate_packet stamps seasonal_band, pattern_confidence, forest_proximity,
  afterglow_decay onto the packet
- annotate_packet returns a NEW frozen HydroPacket (does not mutate original)
- annotate_packet is idempotent: already-annotated packets are returned unchanged
- annotate_packet fails open: if seasonal_prior raises, returns original packet
- illuminate() still works correctly post-refactor (post-dispatch labeling)
"""

from __future__ import annotations

from signal_core.core.lighthouse import annotate_packet, illuminate
from signal_core.core.hydro_types import HydroPacket, DispatchDecision, Route

T_FIXED = 1705320000.0  # Jan 15, 2024 UTC — deep winter


def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id="pkt-lh-001",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.75},
        provenance={"source": "test"},
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


def _decision(route: Route = Route.MAIN) -> DispatchDecision:
    return DispatchDecision(
        route=route, rule_id="D1_MAIN_OPERATIONAL", pressure_class="operational"
    )


# ------------------------------------------------------------------
# annotate_packet
# ------------------------------------------------------------------


class TestAnnotatePacket:
    def test_returns_hydro_packet(self):
        result = annotate_packet(_packet())
        assert isinstance(result, HydroPacket)

    def test_stamps_seasonal_band(self):
        result = annotate_packet(_packet())
        assert result.seasonal_band is not None
        assert result.seasonal_band in (
            "winter",
            "spring_transition",
            "summer",
            "fall_transition",
        )

    def test_stamps_pattern_confidence(self):
        result = annotate_packet(_packet())
        assert result.pattern_confidence is not None
        assert 0.0 <= result.pattern_confidence <= 1.0

    def test_stamps_forest_proximity(self):
        result = annotate_packet(_packet())
        assert result.forest_proximity is not None
        assert 0.0 <= result.forest_proximity <= 1.0

    def test_stamps_afterglow_decay(self):
        result = annotate_packet(_packet())
        assert result.afterglow_decay is not None
        assert 0.2 <= result.afterglow_decay <= 0.9

    def test_does_not_mutate_original(self):
        original = _packet()
        assert original.seasonal_band is None
        annotate_packet(original)
        assert original.seasonal_band is None  # frozen — unchanged

    def test_preserves_original_fields(self):
        original = _packet(lane="natural", domain="natural")
        result = annotate_packet(original)
        assert result.packet_id == original.packet_id
        assert result.lane == original.lane
        assert result.domain == original.domain
        assert result.t == original.t

    def test_idempotent_already_annotated(self):
        first = annotate_packet(_packet())
        second = annotate_packet(first)
        assert second is first  # same object returned

    def test_jan_ts_produces_winter_band(self):
        result = annotate_packet(_packet(t=T_FIXED))
        assert result.seasonal_band == "winter"

    def test_july_ts_produces_summer_band(self):
        from datetime import datetime, timezone

        july_ts = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        result = annotate_packet(_packet(t=july_ts))
        assert result.seasonal_band == "summer"

    def test_fail_open_on_bad_timestamp(self, monkeypatch):
        import signal_core.core.lighthouse as lh_mod

        monkeypatch.setattr(
            lh_mod,
            "compute_seasonal_prior",
            lambda t: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        original = _packet()
        result = annotate_packet(original)
        # Should return original unchanged (fail-open)
        assert result is original


# ------------------------------------------------------------------
# illuminate (post-dispatch, existing behavior preserved)
# ------------------------------------------------------------------


class TestIlluminate:
    def test_main_route_not_hypothesis(self):
        summary = illuminate(_packet(), _decision(Route.MAIN))
        assert summary.hypothesis is False
        assert summary.route == "MAIN"

    def test_turbine_route_is_hypothesis(self):
        summary = illuminate(_packet(), _decision(Route.TURBINE))
        assert summary.hypothesis is True
        assert "exploratory" in summary.note

    def test_spillway_route_is_hypothesis(self):
        summary = illuminate(_packet(), _decision(Route.SPILLWAY))
        assert summary.hypothesis is True
        assert "spillway" in summary.note.lower() or "pressure" in summary.note.lower()

    def test_features_include_packet_fields(self):
        summary = illuminate(_packet(lane="natural", domain="natural"), _decision())
        assert summary.features["lane"] == "natural"
        assert summary.features["domain"] == "natural"
