"""
Tests for rhythm_os.core.wave.wave

Invariants:
- Wave.create() produces a Wave with correct integrity_hash
- Two Waves with identical params produce identical hashes
- Changing any single field changes the hash
- verify_integrity() is True for freshly created Waves
- Wave serializes to valid JSON and round-trips via from_json without loss
- Couplings are immutable (MappingProxyType) after construction
- Boundary values (zero amplitude, empty couplings) are handled
"""

from __future__ import annotations

import json
import pytest
from types import MappingProxyType

from rhythm_os.core.wave.wave import (
    Wave,
    _fmt_float,
    _canonical_couplings,
)

FIXED_TS = "2025-01-15T12:00:00+00:00"


def _wave(**overrides) -> Wave:
    defaults = dict(
        text="test signal",
        signal_type="test",
        phase=1.0,
        frequency=2.0,
        amplitude=0.75,
        afterglow_decay=0.5,
        couplings={"a": 0.3},
        timestamp=FIXED_TS,
    )
    defaults.update(overrides)
    return Wave.create(**defaults)


# ------------------------------------------------------------------
# _fmt_float
# ------------------------------------------------------------------


class TestFmtFloat:
    def test_basic_float(self):
        assert _fmt_float(1.5) == "1.5"

    def test_zero(self):
        assert _fmt_float(0.0) == "0"

    def test_negative(self):
        assert _fmt_float(-3.14) == "-3.14"

    def test_large_integer_like(self):
        result = _fmt_float(1000.0)
        assert "1000" in result


# ------------------------------------------------------------------
# _canonical_couplings
# ------------------------------------------------------------------


class TestCanonicalCouplings:
    def test_empty(self):
        assert _canonical_couplings({}) == {}

    def test_keys_sorted(self):
        result = _canonical_couplings({"z": 1.0, "a": 2.0})
        assert list(result.keys()) == ["a", "z"]

    def test_values_are_strings(self):
        result = _canonical_couplings({"x": 0.5})
        assert isinstance(result["x"], str)


# ------------------------------------------------------------------
# Wave.create — basic construction
# ------------------------------------------------------------------


class TestWaveCreate:
    def test_returns_wave(self):
        w = _wave()
        assert isinstance(w, Wave)

    def test_integrity_hash_non_empty(self):
        w = _wave()
        assert len(w.integrity_hash) == 64  # SHA-256 hex

    def test_couplings_are_mapping_proxy(self):
        w = _wave(couplings={"a": 0.5})
        assert isinstance(w.couplings, MappingProxyType)

    def test_couplings_immutable(self):
        w = _wave(couplings={"a": 0.5})
        with pytest.raises((TypeError, AttributeError)):
            w.couplings["b"] = 0.9  # type: ignore[index]

    def test_empty_couplings_ok(self):
        w = _wave(couplings={})
        assert w.couplings == {}

    def test_zero_amplitude_ok(self):
        w = _wave(amplitude=0.0)
        assert w.amplitude == 0.0

    def test_timestamp_used_when_provided(self):
        w = _wave(timestamp=FIXED_TS)
        assert w.timestamp == FIXED_TS

    def test_timestamp_auto_when_not_provided(self):
        w = Wave.create(text="x", signal_type="auto")
        assert w.timestamp  # non-empty


# ------------------------------------------------------------------
# Deterministic hashing
# ------------------------------------------------------------------


class TestDeterministicHash:
    def test_same_params_same_hash(self):
        w1 = _wave()
        w2 = _wave()
        assert w1.integrity_hash == w2.integrity_hash

    def test_different_text_different_hash(self):
        w1 = _wave(text="signal A")
        w2 = _wave(text="signal B")
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_phase_different_hash(self):
        w1 = _wave(phase=0.0)
        w2 = _wave(phase=1.0)
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_frequency_different_hash(self):
        w1 = _wave(frequency=1.0)
        w2 = _wave(frequency=2.0)
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_amplitude_different_hash(self):
        w1 = _wave(amplitude=0.5)
        w2 = _wave(amplitude=1.0)
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_afterglow_decay_different_hash(self):
        w1 = _wave(afterglow_decay=0.3)
        w2 = _wave(afterglow_decay=0.7)
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_couplings_different_hash(self):
        w1 = _wave(couplings={"a": 0.1})
        w2 = _wave(couplings={"a": 0.9})
        assert w1.integrity_hash != w2.integrity_hash

    def test_different_signal_type_different_hash(self):
        w1 = _wave(signal_type="type_a")
        w2 = _wave(signal_type="type_b")
        assert w1.integrity_hash != w2.integrity_hash


# ------------------------------------------------------------------
# verify_integrity
# ------------------------------------------------------------------


class TestVerifyIntegrity:
    def test_fresh_wave_passes(self):
        w = _wave()
        assert w.verify_integrity() is True

    def test_tampered_hash_fails(self):
        w = _wave()
        # Manually build a Wave with a wrong hash
        tampered = Wave(
            signal_type=w.signal_type,
            phase=w.phase,
            frequency=w.frequency,
            amplitude=w.amplitude,
            afterglow_decay=w.afterglow_decay,
            timestamp=w.timestamp,
            couplings=dict(w.couplings),
            text_content=w.text_content,
            integrity_hash="0" * 64,
        )
        assert tampered.verify_integrity() is False


# ------------------------------------------------------------------
# Serialization round-trip
# ------------------------------------------------------------------


class TestSerialization:
    def test_to_json_produces_valid_json(self):
        w = _wave()
        parsed = json.loads(w.to_json())
        assert isinstance(parsed, dict)

    def test_to_json_contains_all_fields(self):
        w = _wave()
        parsed = json.loads(w.to_json())
        for field in (
            "signal_type",
            "phase",
            "frequency",
            "amplitude",
            "afterglow_decay",
            "timestamp",
            "couplings",
            "text_content",
            "integrity_hash",
        ):
            assert field in parsed

    def test_round_trip_preserves_hash(self):
        w = _wave()
        restored = Wave.from_json(w.to_json())
        assert restored.integrity_hash == w.integrity_hash

    def test_round_trip_integrity_valid(self):
        w = _wave()
        restored = Wave.from_json(w.to_json())
        assert restored.verify_integrity() is True

    def test_round_trip_preserves_couplings(self):
        w = _wave(couplings={"x": 0.25, "y": 0.75})
        restored = Wave.from_json(w.to_json())
        assert dict(restored.couplings) == {"x": 0.25, "y": 0.75}

    def test_round_trip_empty_couplings(self):
        w = _wave(couplings={})
        restored = Wave.from_json(w.to_json())
        assert dict(restored.couplings) == {}
