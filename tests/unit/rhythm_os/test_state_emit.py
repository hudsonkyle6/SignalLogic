"""
Tests for rhythm_os.runtime.antifragile.state_emit

Modules covered:
- _safe_float             (NaN-safe float coercion)
- emit_antifragile_state  (full emission pipeline, mocked I/O)

Invariants:
- _safe_float returns None for NaN, non-numeric, and exceptions
- _safe_float returns the float value for valid inputs
- emit_antifragile_state returns early when bus has insufficient history
- emit_antifragile_state calls append_domain_wave for each valid channel
- emit_antifragile_state skips channels already emitted at t_ref
- emit_antifragile_state clamps emitted values to [0, 1]
- drift_index only emitted when emit_drift_if_missing=True
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from rhythm_os.runtime.antifragile.state_emit import _safe_float, emit_antifragile_state
from rhythm_os.psr.domain_wave import DomainWave


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    def test_valid_int_returns_float(self):
        assert _safe_float(42) == pytest.approx(42.0)

    def test_valid_float_returned(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_valid_string_float_returned(self):
        assert _safe_float("1.5") == pytest.approx(1.5)

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_non_numeric_string_returns_none(self):
        assert _safe_float("not_a_number") is None

    def test_zero_returned(self):
        assert _safe_float(0) == pytest.approx(0.0)

    def test_negative_float_returned(self):
        assert _safe_float(-1.5) == pytest.approx(-1.5)

    def test_object_without_float_returns_none(self):
        class _Bad:
            def __float__(self):
                raise TypeError("no float")

        assert _safe_float(_Bad()) is None


# ---------------------------------------------------------------------------
# Helpers for emit_antifragile_state tests
# ---------------------------------------------------------------------------


_EXTRACTOR = {"method": "test"}
_T_REF = 1705276800.0  # 2024-01-15 00:00:00 UTC


def _make_wave(
    domain: str = "src_domain", channel: str = "src_channel", phase_diff: float = 0.5
) -> DomainWave:
    return DomainWave(
        t=_T_REF,
        domain=domain,
        channel=channel,
        field_cycle="diurnal",
        phase_external=0.0,
        phase_field=0.0,
        phase_diff=phase_diff,
        coherence=0.8,
        extractor=_EXTRACTOR,
    )


def _enough_waves(
    n: int = 15, domain: str = "src_domain", channel: str = "src_channel"
) -> List[DomainWave]:
    """Return enough waves to pass the history/baseline threshold."""
    return [
        _make_wave(domain=domain, channel=channel, phase_diff=0.3 + 0.01 * i)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# emit_antifragile_state — mocked I/O
# ---------------------------------------------------------------------------


class TestEmitAntifragileState:
    def _call(self, waves, *, emit_drift=False, has_emission_return=False, **kwargs):
        """Call emit_antifragile_state with fully mocked I/O."""
        appended = []

        with (
            patch(
                "rhythm_os.runtime.antifragile.state_emit.load_recent_domain_waves",
                return_value=waves,
            ),
            patch(
                "rhythm_os.runtime.antifragile.state_emit.has_emission_at_time",
                return_value=has_emission_return,
            ),
            patch(
                "rhythm_os.runtime.antifragile.state_emit.append_domain_wave",
                side_effect=lambda path, wave: appended.append(wave),
            ),
            patch(
                "rhythm_os.runtime.antifragile.state_emit.today_bus_file",
                return_value=Path("/tmp/fake_bus/2024-01-15.jsonl"),
            ),
        ):
            emit_antifragile_state(
                bus_dir=Path("/tmp/fake_bus"),
                t_ref=_T_REF,
                history_window_sec=3600.0,
                source_domain="src_domain",
                source_channel="src_channel",
                rest_factor=0.0,  # pass float to avoid type error with default "none"
                emit_drift_if_missing=emit_drift,
                **kwargs,
            )

        return appended

    def test_empty_bus_emits_nothing(self):
        appended = self._call([])
        assert appended == []

    def test_insufficient_history_emits_nothing(self):
        # Only 1 wave — below the minimum of 2
        waves = [_make_wave()]
        appended = self._call(waves)
        assert appended == []

    def test_sufficient_history_emits_channels(self):
        waves = _enough_waves(15)
        appended = self._call(waves)
        channels = {w.channel for w in appended}
        # Should emit at least unknowns_index, strain_index, brittleness_index
        assert "unknowns_index" in channels
        assert "strain_index" in channels
        assert "brittleness_index" in channels

    def test_drift_not_emitted_by_default(self):
        waves = _enough_waves(15)
        appended = self._call(waves, emit_drift=False)
        channels = {w.channel for w in appended}
        assert "drift_index" not in channels

    def test_drift_emitted_when_flag_set(self):
        waves = _enough_waves(15)
        appended = self._call(waves, emit_drift=True)
        channels = {w.channel for w in appended}
        assert "drift_index" in channels

    def test_skips_already_emitted_channels(self):
        waves = _enough_waves(15)
        # Simulate all channels already emitted
        appended = self._call(waves, has_emission_return=True)
        assert appended == []

    def test_emitted_values_in_0_1(self):
        waves = _enough_waves(15)
        appended = self._call(waves)
        for w in appended:
            assert 0.0 <= w.phase_diff <= 1.0, (
                f"{w.channel}: {w.phase_diff} out of range"
            )

    def test_emitted_domain_is_antifragile(self):
        waves = _enough_waves(15)
        appended = self._call(waves)
        for w in appended:
            assert w.domain == "antifragile"

    def test_non_matching_domain_waves_ignored(self):
        """Waves from a different domain/channel should not be used."""
        waves = _enough_waves(15, domain="other_domain", channel="other_channel")
        appended = self._call(waves)
        # No matching source domain/channel → emits nothing
        assert appended == []

    def test_nan_phase_diff_waves_skipped(self):
        """Waves with NaN phase_diff should be filtered out."""
        nan_waves = [_make_wave(phase_diff=float("nan")) for _ in range(15)]
        appended = self._call(nan_waves)
        # All filtered → insufficient series → no emission
        assert appended == []

    def test_custom_cycle_id_used(self):
        waves = _enough_waves(15)
        appended = self._call(waves, cycle_id="my_custom_cycle")
        for w in appended:
            assert w.extractor.get("cycle_id") == "my_custom_cycle"

    def test_auto_cycle_id_generated(self):
        waves = _enough_waves(15)
        appended = self._call(waves, cycle_id=None)
        for w in appended:
            assert "antifragile_state" in w.extractor.get("cycle_id", "")
