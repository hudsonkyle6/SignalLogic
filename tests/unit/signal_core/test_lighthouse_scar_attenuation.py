"""
Tests for signal_core.core.lighthouse.attenuate_with_scars

Covers the previously-uncovered attenuate_with_scars function (lines 90-143).

Invariants:
- Returns packet unchanged when forest_proximity is None
- Returns packet unchanged when no scar exists for the pattern
- Returns packet with reduced forest_proximity when a scar exists
- ever_changed=True reduces attenuation (pattern is alerting)
- changed=True on top of ever_changed reduces attenuation further
- Attenuated forest_proximity is never negative
- Fails open: returns original packet if scar read raises
"""

from __future__ import annotations


from signal_core.core.hydro_types import HydroPacket
from signal_core.core.lighthouse import attenuate_with_scars


T_FIXED = 1705320000.0  # Jan 15, 2024 UTC


def _packet(**overrides) -> HydroPacket:
    defaults = dict(
        t=T_FIXED,
        packet_id="pkt-scar-test",
        lane="system",
        domain="system",
        channel="net_pressure",
        value={"coherence": 0.75},
        provenance={"source": "test"},
        seasonal_band="winter",
        pattern_confidence=0.8,
        forest_proximity=0.6,
        afterglow_decay=0.5,
    )
    defaults.update(overrides)
    return HydroPacket(**defaults)


class TestAttenuateWithScars:
    def test_no_forest_proximity_returns_unchanged(self):
        pkt = _packet(forest_proximity=None)
        result = attenuate_with_scars(pkt)
        assert result is pkt

    def test_no_scar_returns_unchanged(self, monkeypatch):
        import signal_core.core.lighthouse as lh

        monkeypatch.setattr(lh, "get_scar", lambda domain, key: None)
        pkt = _packet(forest_proximity=0.8)
        result = attenuate_with_scars(pkt)
        assert result is pkt

    def test_scar_reduces_forest_proximity(self, monkeypatch):
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        scar = Scar(
            scar_id="abc123",
            domain="system",
            pattern_key="winter:net_pressure",
            pressure=1.0,
            changed=False,
            trigger="forest_proximity",
            first_seen=T_FIXED - 1000,
            last_reinforced=T_FIXED,
            decay_rate=0.05,
            reinforcement_count=3,
            ever_changed=False,
        )
        monkeypatch.setattr(lh, "get_scar", lambda domain, key: scar)

        pkt = _packet(forest_proximity=0.8)
        result = attenuate_with_scars(pkt)
        assert result.forest_proximity < pkt.forest_proximity

    def test_attenuation_non_negative(self, monkeypatch):
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        scar = Scar(
            scar_id="abc123",
            domain="system",
            pattern_key="winter:net_pressure",
            pressure=2.0,  # max pressure
            changed=True,
            trigger="forest_proximity",
            first_seen=T_FIXED - 1000,
            last_reinforced=T_FIXED,
            decay_rate=0.05,
            reinforcement_count=10,
            ever_changed=True,
        )
        monkeypatch.setattr(lh, "get_scar", lambda domain, key: scar)

        pkt = _packet(forest_proximity=0.5)
        result = attenuate_with_scars(pkt)
        assert result.forest_proximity >= 0.0

    def test_ever_changed_reduces_attenuation(self, monkeypatch):
        """ever_changed=True means the system stays more alert — less attenuation."""
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        def _scar(ever_changed, changed):
            return Scar(
                scar_id="abc",
                domain="system",
                pattern_key="winter:net_pressure",
                pressure=1.0,
                changed=changed,
                trigger="forest_proximity",
                first_seen=T_FIXED,
                last_reinforced=T_FIXED,
                decay_rate=0.05,
                reinforcement_count=3,
                ever_changed=ever_changed,
            )

        pkt = _packet(forest_proximity=0.8)

        # ever_changed=False → higher attenuation → lower proximity
        monkeypatch.setattr(lh, "get_scar", lambda d, k: _scar(False, False))
        result_plain = attenuate_with_scars(pkt)

        # ever_changed=True → reduced attenuation → higher proximity
        monkeypatch.setattr(lh, "get_scar", lambda d, k: _scar(True, False))
        result_alert = attenuate_with_scars(pkt)

        assert result_alert.forest_proximity > result_plain.forest_proximity

    def test_changed_reduces_attenuation_further(self, monkeypatch):
        """changed=True (recent action) reduces attenuation more than ever_changed alone."""
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        def _scar(changed):
            return Scar(
                scar_id="abc",
                domain="system",
                pattern_key="winter:net_pressure",
                pressure=1.0,
                changed=changed,
                trigger="forest_proximity",
                first_seen=T_FIXED,
                last_reinforced=T_FIXED,
                decay_rate=0.05,
                reinforcement_count=3,
                ever_changed=True,
            )

        pkt = _packet(forest_proximity=0.8)

        monkeypatch.setattr(lh, "get_scar", lambda d, k: _scar(False))
        result_no_recent = attenuate_with_scars(pkt)

        monkeypatch.setattr(lh, "get_scar", lambda d, k: _scar(True))
        result_recent = attenuate_with_scars(pkt)

        # changed=True → less attenuation → higher remaining proximity
        assert result_recent.forest_proximity > result_no_recent.forest_proximity

    def test_fail_open_on_scar_error(self, monkeypatch):
        import signal_core.core.lighthouse as lh

        monkeypatch.setattr(
            lh, "get_scar", lambda d, k: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        pkt = _packet(forest_proximity=0.8)
        result = attenuate_with_scars(pkt)
        # Should return original packet unchanged on error
        assert result is pkt

    def test_no_pattern_confidence_defaults_to_one(self, monkeypatch):
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        scar = Scar(
            scar_id="abc",
            domain="system",
            pattern_key="winter:net_pressure",
            pressure=0.5,
            changed=False,
            trigger="forest_proximity",
            first_seen=T_FIXED,
            last_reinforced=T_FIXED,
            decay_rate=0.05,
            reinforcement_count=1,
            ever_changed=False,
        )
        monkeypatch.setattr(lh, "get_scar", lambda d, k: scar)

        pkt = _packet(forest_proximity=0.8, pattern_confidence=None)
        result = attenuate_with_scars(pkt)
        # Should not raise; attenuation applied with confidence=1.0
        assert isinstance(result, HydroPacket)

    def test_returns_new_packet_not_original(self, monkeypatch):
        import signal_core.core.lighthouse as lh
        from rhythm_os.core.memory.scar import Scar

        scar = Scar(
            scar_id="abc",
            domain="system",
            pattern_key="winter:net_pressure",
            pressure=1.0,
            changed=False,
            trigger="forest_proximity",
            first_seen=T_FIXED,
            last_reinforced=T_FIXED,
            decay_rate=0.05,
            reinforcement_count=2,
            ever_changed=False,
        )
        monkeypatch.setattr(lh, "get_scar", lambda d, k: scar)

        pkt = _packet(forest_proximity=0.8)
        result = attenuate_with_scars(pkt)
        assert result is not pkt
