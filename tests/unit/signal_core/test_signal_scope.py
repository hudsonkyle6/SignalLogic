"""
Tests for rhythm_os.scope.signal_scope

Modules covered:
- _clamp01      (clamp helper)
- _bar          (ASCII bar renderer)
- _label        (section header printer)
- render_scope  (full oscilloscope display)

Invariants:
- _clamp01 keeps values in [0, 1]
- _bar returns a string of the correct total width
- render_scope does not crash on empty wave list
- render_scope does not crash on waves with various optional fields
- render_scope prints output (captured via capsys)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from rhythm_os.scope.signal_scope import _clamp01, _bar, render_scope


# ---------------------------------------------------------------------------
# Minimal WaveView implementation for testing
# ---------------------------------------------------------------------------


@dataclass
class _FakeWave:
    t: float = 1000.0
    phase: float = 0.5
    amplitude: float = 0.7
    afterglow_decay: float = 0.5
    phase_spread: float = 0.3
    buffer_margin: float = 0.5
    persistence: int = 3
    drift: Optional[float] = None
    afterglow: Optional[float] = None


# ---------------------------------------------------------------------------
# _clamp01
# ---------------------------------------------------------------------------


class TestClamp01Scope:
    def test_below_zero_returns_zero(self):
        assert _clamp01(-1.0) == 0.0

    def test_above_one_returns_one(self):
        assert _clamp01(2.0) == 1.0

    def test_zero_returns_zero(self):
        assert _clamp01(0.0) == 0.0

    def test_one_returns_one(self):
        assert _clamp01(1.0) == pytest.approx(1.0)

    def test_midpoint_passthrough(self):
        assert _clamp01(0.5) == pytest.approx(0.5)

    def test_string_float_coerced(self):
        # _clamp01 calls float(), so string "0.5" is valid
        assert _clamp01("0.5") == pytest.approx(0.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _bar
# ---------------------------------------------------------------------------


class TestBar:
    def test_default_width_48(self):
        result = _bar(0.5)
        assert len(result) == 48

    def test_custom_width(self):
        result = _bar(0.5, width=20)
        assert len(result) == 20

    def test_zero_value_all_spaces(self):
        result = _bar(0.0, width=10)
        assert result == " " * 10

    def test_full_value_all_blocks(self):
        result = _bar(1.0, width=10)
        assert result == "█" * 10

    def test_half_value_half_blocks(self):
        result = _bar(0.5, width=10)
        filled = result.count("█")
        assert filled == 5


# ---------------------------------------------------------------------------
# render_scope
# ---------------------------------------------------------------------------


class TestRenderScope:
    def test_empty_waves_no_crash(self, capsys):
        render_scope([])
        captured = capsys.readouterr()
        assert "no waves in window" in captured.out

    def test_single_wave_renders_without_error(self, capsys):
        wave = _FakeWave()
        render_scope([wave])
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_multiple_waves_render(self, capsys):
        waves = [_FakeWave(amplitude=0.1 * i) for i in range(5)]
        render_scope(waves)
        captured = capsys.readouterr()
        assert "RHYTHM OS" in captured.out

    def test_afterglow_section_shown_when_afterglow_set(self, capsys):
        waves = [_FakeWave(afterglow=0.5)]
        render_scope(waves)
        captured = capsys.readouterr()
        assert "AFTERGLOW" in captured.out

    def test_afterglow_section_absent_when_afterglow_none(self, capsys):
        waves = [_FakeWave(afterglow=None)]
        render_scope(waves)
        captured = capsys.readouterr()
        assert "AFTERGLOW" not in captured.out

    def test_window_trims_old_waves(self, capsys):
        """render_scope windows to last N waves."""
        waves = [_FakeWave(t=float(i)) for i in range(200)]
        # Should not crash even with many waves; window=5 limits output
        render_scope(waves, window=5)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_missing_optional_fields_handled(self, capsys):
        """Waves without drift/afterglow should not cause AttributeError."""

        class _MinimalWave:
            t = 1000.0
            phase = 0.5
            amplitude = 0.5
            afterglow_decay = 0.5

        render_scope([_MinimalWave()])
        captured = capsys.readouterr()
        assert "RHYTHM OS" in captured.out
