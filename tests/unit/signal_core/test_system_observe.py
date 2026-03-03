"""
Tests for signal_core.core.instruments.system_observe

Modules covered:
- _clamp01        (clamp helper)
- _bootstrap_packet (fallback packet when psutil unavailable)
- sample_once     (live system snapshot via psutil or fallback)

Invariants:
- _clamp01 keeps values in [0, 1]
- _bootstrap_packet always returns a valid HydroPacket
- sample_once returns a HydroPacket in all cases
- Fallback packet produced on psutil ImportError
- Fallback packet produced when psutil raises during sampling
- rate field is in [0, 1]
"""

from __future__ import annotations

import pytest

from signal_core.core.hydro_types import HydroPacket
from signal_core.core.instruments.system_observe import (
    _clamp01,
    _bootstrap_packet,
    sample_once,
)


# ---------------------------------------------------------------------------
# _clamp01
# ---------------------------------------------------------------------------


class TestClamp01:
    def test_below_zero_clamps_to_zero(self):
        assert _clamp01(-5.0) == 0.0

    def test_above_one_clamps_to_one(self):
        assert _clamp01(2.0) == 1.0

    def test_midpoint_passthrough(self):
        assert _clamp01(0.5) == pytest.approx(0.5)

    def test_zero_is_zero(self):
        assert _clamp01(0.0) == 0.0

    def test_one_is_one(self):
        assert _clamp01(1.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _bootstrap_packet
# ---------------------------------------------------------------------------


class TestBootstrapPacket:
    def test_returns_hydro_packet(self):
        pkt = _bootstrap_packet(1000.0)
        assert isinstance(pkt, HydroPacket)

    def test_t_matches_input(self):
        pkt = _bootstrap_packet(9999.0)
        assert pkt.t == pytest.approx(9999.0)

    def test_lane_is_system(self):
        pkt = _bootstrap_packet(1000.0)
        assert pkt.lane == "system"

    def test_channel_is_bootstrap(self):
        pkt = _bootstrap_packet(1000.0)
        assert pkt.channel == "bootstrap"

    def test_packet_id_is_string(self):
        pkt = _bootstrap_packet(1000.0)
        assert isinstance(pkt.packet_id, str)
        assert len(pkt.packet_id) > 0

    def test_replay_is_false(self):
        pkt = _bootstrap_packet(1000.0)
        assert pkt.replay is False

    def test_anomaly_flag_is_false(self):
        pkt = _bootstrap_packet(1000.0)
        assert pkt.anomaly_flag is False


# ---------------------------------------------------------------------------
# sample_once
# ---------------------------------------------------------------------------


class TestSampleOnce:
    def test_returns_hydro_packet(self):
        pkt = sample_once()
        assert isinstance(pkt, HydroPacket)

    def test_lane_is_system(self):
        pkt = sample_once()
        assert pkt.lane == "system"

    def test_domain_is_core(self):
        pkt = sample_once()
        assert pkt.domain == "core"

    def test_packet_id_non_empty(self):
        pkt = sample_once()
        assert isinstance(pkt.packet_id, str)
        assert len(pkt.packet_id) > 0

    def test_replay_is_false(self):
        pkt = sample_once()
        assert pkt.replay is False

    def test_rate_in_0_1(self):
        pkt = sample_once()
        if pkt.rate is not None:
            assert 0.0 <= pkt.rate <= 1.0

    def test_fallback_when_psutil_missing(self, monkeypatch):
        import signal_core.core.instruments.system_observe as mod

        monkeypatch.setattr(mod, "_HAS_PSUTIL", False)
        pkt = sample_once()
        assert isinstance(pkt, HydroPacket)
        assert pkt.channel == "bootstrap"

    def test_fallback_when_psutil_raises(self, monkeypatch):
        import signal_core.core.instruments.system_observe as mod

        monkeypatch.setattr(mod, "_HAS_PSUTIL", True)

        # Patch the psutil module attribute used inside the function
        import signal_core.core.instruments.system_observe as observe_mod

        def _bad_cpu(*args, **kwargs):
            raise RuntimeError("psutil exploded")

        monkeypatch.setattr(observe_mod._psutil, "cpu_percent", _bad_cpu)
        pkt = sample_once()
        # Should fall back to bootstrap
        assert isinstance(pkt, HydroPacket)
