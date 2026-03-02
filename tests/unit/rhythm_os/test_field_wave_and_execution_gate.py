"""
Tests for:
  - rhythm_os.core.field_wave.FieldWave
  - rhythm_os.foundations_runtime.execution_gate.ExecutionGateDecision
"""
from __future__ import annotations

import cmath
import math

import pytest

from rhythm_os.core.field_wave import FieldWave
from rhythm_os.foundations_runtime.execution_gate import ExecutionGateDecision


# ---------------------------------------------------------------------------
# FieldWave
# ---------------------------------------------------------------------------

class TestFieldWave:
    def _wave(self, **overrides):
        defaults = dict(
            t=1_700_000_000.0,
            cycle="diurnal",
            phase=0.5,
            sine=math.sin(0.5),
            phasor=cmath.exp(1j * 0.5),
        )
        defaults.update(overrides)
        return FieldWave(**defaults)

    def test_construction(self):
        w = self._wave()
        assert w.t == 1_700_000_000.0
        assert w.cycle == "diurnal"

    def test_frozen(self):
        w = self._wave()
        with pytest.raises((AttributeError, TypeError)):
            w.phase = 1.0  # type: ignore[misc]

    @pytest.mark.parametrize("cycle", ["diurnal", "semi_diurnal", "seasonal", "longwave"])
    def test_valid_cycle_names(self, cycle):
        w = self._wave(cycle=cycle)
        assert w.cycle == cycle

    def test_phase_preserved(self):
        w = self._wave(phase=1.234)
        assert w.phase == pytest.approx(1.234)

    def test_phasor_is_complex(self):
        w = self._wave()
        assert isinstance(w.phasor, complex)

    def test_sine_is_float(self):
        w = self._wave()
        assert isinstance(w.sine, float)

    def test_equality(self):
        a = self._wave(t=1.0)
        b = self._wave(t=1.0)
        assert a == b

    def test_inequality_different_t(self):
        a = self._wave(t=1.0)
        b = self._wave(t=2.0)
        assert a != b


# ---------------------------------------------------------------------------
# ExecutionGateDecision
# ---------------------------------------------------------------------------

class TestExecutionGateDecision:
    def test_open_state(self):
        d = ExecutionGateDecision(state="OPEN", reason="all systems nominal")
        assert d.state == "OPEN"
        assert d.reason == "all systems nominal"

    def test_closed_state(self):
        d = ExecutionGateDecision(state="CLOSED", reason="readiness check failed")
        assert d.state == "CLOSED"

    def test_frozen(self):
        d = ExecutionGateDecision(state="OPEN", reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            d.state = "CLOSED"  # type: ignore[misc]

    def test_equality(self):
        a = ExecutionGateDecision(state="OPEN", reason="ok")
        b = ExecutionGateDecision(state="OPEN", reason="ok")
        assert a == b

    def test_inequality_different_state(self):
        a = ExecutionGateDecision(state="OPEN", reason="ok")
        b = ExecutionGateDecision(state="CLOSED", reason="ok")
        assert a != b

    def test_inequality_different_reason(self):
        a = ExecutionGateDecision(state="OPEN", reason="reason A")
        b = ExecutionGateDecision(state="OPEN", reason="reason B")
        assert a != b
