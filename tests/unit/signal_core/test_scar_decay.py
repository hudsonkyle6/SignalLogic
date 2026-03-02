"""
Tests for time-proportional decay in rhythm_os.core.memory.scar

Invariants:
- apply_decay with 0 elapsed time applies no meaningful decay
- apply_decay with 1 reference cycle (3600s) applies exactly one decay step
- apply_decay with 2 reference cycles applies two compounded decay steps
- Calling apply_decay twice in quick succession does not double-decay
- last_decayed is updated after each apply_decay call
- Scars below PRUNE_THRESHOLD after decay are pruned
- write_scar stamps last_decayed = now
- Old scars without last_decayed (last_decayed == 0) fall back to last_reinforced
"""

from __future__ import annotations

import json
import time
import pytest

import rhythm_os.core.memory.scar as scar_mod
from rhythm_os.core.memory.scar import (
    Scar,
    apply_decay,
    apply_all_decay,
    write_scar,
    get_scar,
    DECAY_RATE_DEFAULT,
    PRUNE_THRESHOLD,
    _REFERENCE_CYCLE_SECONDS,
    _scar_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_raw_scar(tmp_path, domain: str, scar: Scar) -> None:
    """Write a scar directly to the domain file, bypassing the public API."""
    path = tmp_path / f"{domain}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(scar.to_dict()) + "\n")


_TEST_KEY = "summer:net_pressure"


def _make_scar(
    domain: str = "system",
    pressure: float = 1.0,
    decay_rate: float = DECAY_RATE_DEFAULT,
    last_reinforced: float | None = None,
    last_decayed: float = 0.0,
) -> Scar:
    now = time.time()
    return Scar(
        scar_id=_scar_id(domain, _TEST_KEY),
        domain=domain,
        pattern_key=_TEST_KEY,
        pressure=pressure,
        changed=False,
        ever_changed=False,
        trigger="forest_proximity",
        first_seen=now,
        last_reinforced=last_reinforced if last_reinforced is not None else now,
        last_decayed=last_decayed,
        decay_rate=decay_rate,
        reinforcement_count=1,
    )


# ---------------------------------------------------------------------------
# Time-proportional decay
# ---------------------------------------------------------------------------


class TestTimeProportionalDecay:
    def test_zero_elapsed_no_meaningful_decay(self, tmp_path, monkeypatch):
        """Scars decayed immediately after creation lose negligible pressure."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        now = time.time()
        scar = _make_scar(domain=domain, pressure=1.0, last_decayed=now)
        _write_raw_scar(tmp_path, domain, scar)

        apply_decay(domain)

        result = get_scar(domain, _TEST_KEY)
        # elapsed ~ 0ms → almost no decay
        assert result is not None
        assert result.pressure == pytest.approx(1.0, abs=0.001)

    def test_one_reference_cycle_applies_one_decay_step(self, tmp_path, monkeypatch):
        """
        After exactly one reference cycle (3600s) elapsed, pressure should be
        pressure * (1 - decay_rate)^1.
        """
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        rate = 0.05
        initial = 1.0
        baseline = time.time() - _REFERENCE_CYCLE_SECONDS  # 1 hour ago

        scar = _make_scar(
            domain=domain, pressure=initial, decay_rate=rate, last_decayed=baseline
        )
        _write_raw_scar(tmp_path, domain, scar)

        apply_decay(domain)

        result = get_scar(domain, _TEST_KEY)
        assert result is not None
        expected = initial * (1.0 - rate) ** 1.0
        assert result.pressure == pytest.approx(expected, rel=0.01)

    def test_two_reference_cycles_compounds_correctly(self, tmp_path, monkeypatch):
        """After 2 reference cycles elapsed, pressure = initial * (1-rate)^2."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        rate = 0.05
        initial = 1.0
        baseline = time.time() - 2 * _REFERENCE_CYCLE_SECONDS  # 2 hours ago

        scar = _make_scar(
            domain=domain, pressure=initial, decay_rate=rate, last_decayed=baseline
        )
        _write_raw_scar(tmp_path, domain, scar)

        apply_decay(domain)

        result = get_scar(domain, _TEST_KEY)
        assert result is not None
        expected = initial * (1.0 - rate) ** 2.0
        assert result.pressure == pytest.approx(expected, rel=0.01)

    def test_second_call_does_not_double_decay(self, tmp_path, monkeypatch):
        """
        Calling apply_decay twice in quick succession should only apply the
        second pass's tiny elapsed time, not re-apply the original elapsed time.
        """
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        rate = 0.05
        initial = 1.0
        baseline = time.time() - _REFERENCE_CYCLE_SECONDS  # 1 hour ago

        scar = _make_scar(
            domain=domain, pressure=initial, decay_rate=rate, last_decayed=baseline
        )
        _write_raw_scar(tmp_path, domain, scar)

        apply_decay(domain)  # applies ~1 hour of decay
        after_first = get_scar(domain, _TEST_KEY)

        apply_decay(domain)  # applies only seconds elapsed since first call
        after_second = get_scar(domain, _TEST_KEY)

        assert after_first is not None
        assert after_second is not None
        # Second pass should change pressure by much less than one reference cycle
        ratio = after_second.pressure / after_first.pressure
        assert ratio > 0.999  # less than 0.1% additional decay in microseconds

    def test_last_decayed_updated_after_decay(self, tmp_path, monkeypatch):
        """apply_decay updates last_decayed to approximately now."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        baseline = time.time() - _REFERENCE_CYCLE_SECONDS

        scar = _make_scar(domain=domain, pressure=1.0, last_decayed=baseline)
        _write_raw_scar(tmp_path, domain, scar)

        before = time.time()
        apply_decay(domain)
        after = time.time()

        result = get_scar(domain, _TEST_KEY)
        assert result is not None
        assert before <= result.last_decayed <= after + 1.0

    def test_fallback_to_last_reinforced_for_legacy_scars(self, tmp_path, monkeypatch):
        """
        Scars loaded from old files have last_decayed == 0.0 (default).
        apply_decay should fall back to last_reinforced as the baseline.
        """
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        rate = 0.05
        initial = 1.0
        # last_reinforced = 1 hour ago, last_decayed = 0 (legacy)
        old_reinforced = time.time() - _REFERENCE_CYCLE_SECONDS

        scar = _make_scar(
            domain=domain,
            pressure=initial,
            decay_rate=rate,
            last_reinforced=old_reinforced,
            last_decayed=0.0,  # legacy — never explicitly decayed
        )
        _write_raw_scar(tmp_path, domain, scar)

        apply_decay(domain)

        result = get_scar(domain, _TEST_KEY)
        assert result is not None
        expected = initial * (1.0 - rate) ** 1.0
        assert result.pressure == pytest.approx(expected, rel=0.01)

    def test_pressure_below_threshold_pruned(self, tmp_path, monkeypatch):
        """Scars that decay below PRUNE_THRESHOLD are removed."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        domain = "system"
        # Tiny pressure: one reference cycle will push it below threshold
        tiny = PRUNE_THRESHOLD * 0.5
        baseline = time.time() - _REFERENCE_CYCLE_SECONDS

        scar = _make_scar(domain=domain, pressure=tiny, last_decayed=baseline)
        _write_raw_scar(tmp_path, domain, scar)

        pruned = apply_decay(domain)

        assert pruned == 1
        assert get_scar(domain, _TEST_KEY) is None


# ---------------------------------------------------------------------------
# write_scar stamps last_decayed
# ---------------------------------------------------------------------------


class TestWriteScarTimestamps:
    def test_write_scar_stamps_last_decayed(self, tmp_path, monkeypatch):
        """write_scar sets last_decayed ≈ now on newly created scars."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        before = time.time()
        write_scar(
            domain="system",
            key="summer:net_pressure",
            pressure_delta=0.5,
            changed=True,
            trigger="forest_proximity",
        )
        after = time.time()

        scar = get_scar("system", "summer:net_pressure")
        assert scar is not None
        assert before <= scar.last_decayed <= after + 1.0

    def test_write_scar_resets_last_decayed_on_reinforce(self, tmp_path, monkeypatch):
        """Reinforcing an existing scar resets last_decayed to now."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)

        write_scar(
            domain="system",
            key="summer:net_pressure",
            pressure_delta=0.5,
            changed=True,
            trigger="forest_proximity",
        )

        before = time.time()
        write_scar(
            domain="system",
            key="summer:net_pressure",
            pressure_delta=0.3,
            changed=False,
            trigger="forest_proximity",
        )
        after = time.time()

        scar = get_scar("system", "summer:net_pressure")
        assert scar is not None
        assert before <= scar.last_decayed <= after + 1.0


# ---------------------------------------------------------------------------
# apply_all_decay
# ---------------------------------------------------------------------------


class TestApplyAllDecay:
    def test_apply_all_decay_covers_multiple_domains(self, tmp_path, monkeypatch):
        """apply_all_decay processes every domain file in SCARS_DIR."""
        monkeypatch.setattr(scar_mod, "SCARS_DIR", tmp_path)
        now = time.time()
        baseline = now - _REFERENCE_CYCLE_SECONDS

        for domain in ("system", "natural", "market"):
            scar = _make_scar(domain=domain, pressure=1.0, last_decayed=baseline)
            _write_raw_scar(tmp_path, domain, scar)

        results = apply_all_decay()

        assert set(results.keys()) == {"system", "natural", "market"}
        for domain in results:
            s = get_scar(domain, _TEST_KEY)
            assert s is not None
            assert s.pressure == pytest.approx(
                1.0 * (1.0 - DECAY_RATE_DEFAULT), rel=0.01
            )
