"""
Tests for signal_core.core.domain_ingress_view.DomainIngressView

Invariants:
- from_domain_wave() maps DomainWave fields to DomainIngressView correctly
- lane is always "domain"
- phase is always the wave's phase_diff
- packet_id encodes domain, channel, and truncated timestamp
- provenance is a copy of extractor dict
"""

from __future__ import annotations

from signal_core.core.domain_ingress_view import DomainIngressView
from rhythm_os.psr.domain_wave import DomainWave

T_FIXED = 1_705_320_000.0


def _wave(**overrides) -> DomainWave:
    defaults = dict(
        t=T_FIXED,
        domain="market",
        channel="vol_pressure",
        field_cycle="diurnal",
        phase_external=0.5,
        phase_field=0.3,
        phase_diff=0.2,
        coherence=0.9,
        extractor={"source": "test", "version": "v1"},
    )
    defaults.update(overrides)
    return DomainWave(**defaults)


def test_from_domain_wave_basic():
    dw = _wave()
    view = DomainIngressView.from_domain_wave(dw)
    assert view.domain == "market"
    assert view.channel == "vol_pressure"
    assert view.lane == "domain"
    assert view.phase == 0.2
    assert view.provenance == {"source": "test", "version": "v1"}


def test_packet_id_format():
    dw = _wave(domain="cyber", channel="cadence_pressure", t=T_FIXED)
    view = DomainIngressView.from_domain_wave(dw)
    assert view.packet_id == f"dw::cyber::cadence_pressure::{int(T_FIXED)}"


def test_phase_is_phase_diff():
    dw = _wave(phase_diff=-0.314)
    view = DomainIngressView.from_domain_wave(dw)
    assert view.phase == -0.314


def test_empty_extractor():
    dw = _wave(extractor=None)
    view = DomainIngressView.from_domain_wave(dw)
    assert view.provenance == {}


def test_lane_is_always_domain():
    for domain in ("market", "system", "cyber", "natural", "human_trafficking"):
        view = DomainIngressView.from_domain_wave(_wave(domain=domain))
        assert view.lane == "domain"
