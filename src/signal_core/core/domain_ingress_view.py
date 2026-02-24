from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from rhythm_os.psr.domain_wave import DomainWave


@dataclass(frozen=True)
class DomainIngressView:
    """
    Minimal structural view required by Hydro Ingress Gate.

    This is:
    - NOT a packet
    - NOT persisted
    - A transient structural adapter

    It exists solely to satisfy Hydro ingress checks.
    """

    packet_id: str
    domain: str
    lane: str
    channel: str
    phase: float
    provenance: Dict[str, str]

    @classmethod
    def from_domain_wave(cls, dw: DomainWave) -> "DomainIngressView":
        return cls(
            packet_id=f"dw::{dw.domain}::{dw.channel}::{int(dw.t)}",
            domain=dw.domain,
            lane="domain",
            channel=dw.channel,
            phase=float(dw.phase_diff),
            provenance=dict(dw.extractor or {}),
        )
