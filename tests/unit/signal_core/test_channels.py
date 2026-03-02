"""
Tests for signal_core.core.channels

Invariants:
- ChannelSink.accept records the packet_id without side effects
- build_channels returns all three required channels: MAIN, SPILLWAY, TURBINE
- Each channel starts with an empty received list
- Multiple accepts accumulate in order
"""

from __future__ import annotations

from signal_core.core.channels import ChannelSink, build_channels
from signal_core.core.hydro_types import HydroPacket


def _packet(packet_id: str = "pkt-001") -> HydroPacket:
    return HydroPacket(
        t=1705320000.0,
        packet_id=packet_id,
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"v": 1},
        provenance={"source": "test"},
    )


class TestChannelSink:
    def test_accept_records_packet_id(self):
        sink = ChannelSink(name="MAIN", received=[])
        sink.accept(_packet("pkt-001"))
        assert sink.received == ["pkt-001"]

    def test_accept_multiple_accumulates_in_order(self):
        sink = ChannelSink(name="TURBINE", received=[])
        sink.accept(_packet("a"))
        sink.accept(_packet("b"))
        sink.accept(_packet("c"))
        assert sink.received == ["a", "b", "c"]

    def test_accept_has_no_return_value(self):
        sink = ChannelSink(name="SPILLWAY", received=[])
        result = sink.accept(_packet())
        assert result is None

    def test_sink_name_preserved(self):
        sink = ChannelSink(name="SPILLWAY", received=[])
        assert sink.name == "SPILLWAY"


class TestBuildChannels:
    def test_returns_all_three_channels(self):
        channels = build_channels()
        assert set(channels.keys()) == {"MAIN", "SPILLWAY", "TURBINE"}

    def test_each_channel_starts_empty(self):
        channels = build_channels()
        for name, sink in channels.items():
            assert sink.received == [], f"{name} should start empty"

    def test_each_channel_name_matches_key(self):
        channels = build_channels()
        for key, sink in channels.items():
            assert sink.name == key

    def test_channels_are_independent_instances(self):
        channels = build_channels()
        channels["MAIN"].accept(_packet("x"))
        assert channels["SPILLWAY"].received == []
        assert channels["TURBINE"].received == []
