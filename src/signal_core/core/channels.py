"""
POSTURE: HYDRO
Sole authority to admit, route, and commit history.
No backflow permitted.
See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .hydro_types import HydroPacket


@dataclass
class ChannelSink:
    name: str
    received: List[str]

    def accept(self, packet: HydroPacket) -> None:
        # No execution. No side effects. Just hold packet ids in memory.
        self.received.append(packet.packet_id)


def build_channels():
    return {
        "MAIN": ChannelSink("MAIN", []),
        "SPILLWAY": ChannelSink("SPILLWAY", []),
        "TURBINE": ChannelSink("TURBINE", []),
    }
