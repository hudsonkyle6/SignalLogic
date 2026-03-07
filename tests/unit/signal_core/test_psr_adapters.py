"""
Tests for psr_tools and rhythm_os adapter modules.

Modules covered:
- psr_tools/_latest_domain_wave.py      (latest_wave filter logic)
- psr_tools/domain_to_cyber_ingress.py  (adapter: read → gate → enqueue)
- psr_tools/domain_to_market_ingress.py
- psr_tools/domain_to_natural_ingress.py
- psr_tools/domain_to_system_ingress.py
- psr_tools/domain_to_trafficking_ingress.py
- psr_tools/domain_to_cyber_attack_ingress.py
- rhythm_os/adapters/observe/phase_compare.py  (wrap_phase, compute_domain_wave)
- rhythm_os/adapters/observe/phase_extractor.py (zero_crossing, unified interface)
- rhythm_os/adapters/observe/synthetic_multi.py (generate_multi_channel_synthetic)
- rhythm_os/core/coupling/coupling.py           (compute_coupling)
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared DomainWave factory
# ---------------------------------------------------------------------------


def _dw(domain: str = "cyber", channel: str = "ch", t: float = 1_705_000_000.0, **kw):
    from rhythm_os.psr.domain_wave import DomainWave

    defaults = dict(
        t=t,
        domain=domain,
        channel=channel,
        field_cycle="diurnal",
        phase_external=1.0,
        phase_field=0.9,
        phase_diff=0.1,
        coherence=0.8,
        extractor={"method": "test"},
    )
    defaults.update(kw)
    return DomainWave(**defaults)


# ===========================================================================
# psr_tools/_latest_domain_wave.py
# ===========================================================================


class TestLatestWave:
    def _call(self, waves, **kw):
        from psr_tools._latest_domain_wave import latest_wave

        return latest_wave(waves, **kw)

    def test_returns_none_for_empty(self):
        assert self._call([], domain="cyber") is None

    def test_returns_only_matching_domain(self):
        w1 = _dw(domain="cyber", t=1000.0)
        w2 = _dw(domain="market", t=2000.0)
        result = self._call([w1, w2], domain="cyber")
        assert result is w1

    def test_returns_latest_by_timestamp(self):
        w1 = _dw(domain="cyber", t=1000.0)
        w2 = _dw(domain="cyber", t=2000.0)
        result = self._call([w1, w2], domain="cyber")
        assert result is w2

    def test_channel_filter(self):
        w1 = _dw(domain="cyber", channel="a", t=1000.0)
        w2 = _dw(domain="cyber", channel="b", t=2000.0)
        result = self._call([w1, w2], domain="cyber", channel="a")
        assert result is w1

    def test_field_cycle_filter(self):
        w1 = _dw(domain="cyber", field_cycle="diurnal", t=1000.0)
        w2 = _dw(domain="cyber", field_cycle="semi_diurnal", t=2000.0)
        result = self._call([w1, w2], domain="cyber", field_cycle="diurnal")
        assert result is w1

    def test_channel_and_field_cycle_combined(self):
        w1 = _dw(domain="cyber", channel="a", field_cycle="diurnal", t=3000.0)
        w2 = _dw(domain="cyber", channel="b", field_cycle="diurnal", t=4000.0)
        result = self._call(
            [w1, w2], domain="cyber", channel="a", field_cycle="diurnal"
        )
        assert result is w1

    def test_no_match_returns_none(self):
        waves = [_dw(domain="market")]
        result = self._call(waves, domain="cyber")
        assert result is None


# ===========================================================================
# rhythm_os/adapters/observe/phase_compare.py
# ===========================================================================


class TestWrapPhase:
    def _call(self, delta):
        from rhythm_os.adapters.observe.phase_compare import wrap_phase

        return wrap_phase(delta)

    def test_zero_stays_zero(self):
        assert self._call(0.0) == pytest.approx(0.0)

    def test_pi_stays_pi(self):
        assert abs(self._call(math.pi)) == pytest.approx(math.pi, abs=1e-9)

    def test_positive_overflow_wrapped(self):
        result = self._call(math.pi + 0.1)
        assert -math.pi <= result <= math.pi

    def test_negative_overflow_wrapped(self):
        result = self._call(-math.pi - 0.1)
        assert -math.pi <= result <= math.pi

    def test_two_pi_wraps_to_zero(self):
        result = self._call(2 * math.pi)
        assert abs(result) < 1e-9


class TestComputeDomainWave:
    # BUG: phase_compare.compute_domain_wave does not pass `field_cycle` to
    # DomainWave.__init__(), so the function always raises TypeError.
    # These tests document the bug; they are xfail until the bug is fixed.

    @pytest.mark.xfail(
        reason="BUG: compute_domain_wave omits field_cycle arg to DomainWave"
    )
    def test_returns_domain_wave(self):
        from rhythm_os.adapters.observe.phase_compare import compute_domain_wave

        result = compute_domain_wave(
            t=1_705_000_000.0,
            domain="test",
            channel="ch",
            phase_external=1.0,
            field_component="semi_diurnal",
            coherence=0.9,
            extractor_meta={"method": "test"},
        )
        assert result.domain == "test"
        assert result.channel == "ch"
        assert result.coherence == pytest.approx(0.9)
        assert -math.pi <= result.phase_diff <= math.pi

    def test_invalid_component_raises(self):
        from rhythm_os.adapters.observe.phase_compare import compute_domain_wave

        with pytest.raises((ValueError, TypeError)):
            compute_domain_wave(
                t=1_705_000_000.0,
                domain="test",
                channel="ch",
                phase_external=1.0,
                field_component="bogus_component",
                coherence=None,
                extractor_meta={},
            )

    @pytest.mark.xfail(
        reason="BUG: compute_domain_wave omits field_cycle arg to DomainWave"
    )
    def test_none_coherence_propagated(self):
        from rhythm_os.adapters.observe.phase_compare import compute_domain_wave

        result = compute_domain_wave(
            t=1_705_000_000.0,
            domain="x",
            channel="y",
            phase_external=0.0,
            field_component="diurnal",
            coherence=None,
            extractor_meta={"method": "none"},
        )
        assert result.coherence is None


# ===========================================================================
# rhythm_os/adapters/observe/phase_extractor.py
# ===========================================================================


class TestWrapPhaseExtractor:
    def test_wrap_phase_modulo(self):
        from rhythm_os.adapters.observe.phase_extractor import _wrap_phase

        result = _wrap_phase(3 * math.pi)
        assert 0.0 <= result < 2 * math.pi


class TestExtractPhaseZeroCrossing:
    def _call(self, samples):
        from rhythm_os.adapters.observe.phase_extractor import (
            extract_phase_zero_crossing,
        )

        return extract_phase_zero_crossing(samples)

    def _sine_samples(self, n: int = 100, period: float = 50.0):
        """Generate simple sine samples for testing."""
        return [(float(i), math.sin(2 * math.pi * i / period)) for i in range(n)]

    def test_raises_insufficient_samples(self):
        with pytest.raises(ValueError, match="Insufficient"):
            self._call([(0.0, 0.0), (1.0, 1.0)])

    def test_returns_phase_and_metadata(self):
        samples = self._sine_samples(100)
        phase, meta = self._call(samples)
        assert isinstance(phase, float)
        assert meta["method"] == "zero_crossing"
        assert 0.0 <= phase < 2 * math.pi

    def test_raises_when_not_enough_crossings(self):
        # Monotonically increasing — no zero crossings
        samples = [(float(i), float(i) + 0.1) for i in range(20)]
        with pytest.raises(ValueError, match="zero crossings|Insufficient"):
            self._call(samples)


class TestExtractExternalPhase:
    def test_zero_crossing_method(self):
        from rhythm_os.adapters.observe.phase_extractor import extract_external_phase

        samples = [(float(i), math.sin(2 * math.pi * i / 50.0)) for i in range(100)]
        phase, meta = extract_external_phase(samples, method="zero_crossing")
        assert 0.0 <= phase < 2 * math.pi
        assert meta["method"] == "zero_crossing"

    def test_unknown_method_raises(self):
        from rhythm_os.adapters.observe.phase_extractor import extract_external_phase

        with pytest.raises(ValueError, match="Unknown phase extraction method"):
            extract_external_phase([], method="bogus")


# ===========================================================================
# rhythm_os/adapters/observe/synthetic_multi.py
# ===========================================================================


class TestGenerateMultiChannelSynthetic:
    def _call(self, channels):
        from rhythm_os.adapters.observe.synthetic_multi import (
            generate_multi_channel_synthetic,
        )

        return generate_multi_channel_synthetic(
            t_now=1_705_000_000.0,
            channels=channels,
        )

    def test_empty_channels_returns_empty(self):
        result = self._call([])
        assert result == []

    def test_one_channel_produces_one_wave(self):
        from rhythm_os.adapters.observe.synthetic_multi import SyntheticChannelSpec

        ch = SyntheticChannelSpec(name="ch_a", phase_offset_deg=0.0)
        result = self._call([ch])
        assert len(result) == 1
        assert result[0].channel == "ch_a"
        assert result[0].domain == "synthetic"

    def test_phase_diff_in_bounds(self):
        from rhythm_os.adapters.observe.synthetic_multi import SyntheticChannelSpec

        ch = SyntheticChannelSpec(name="ch_b", phase_offset_deg=45.0)
        result = self._call([ch])
        wave = result[0]
        assert -math.pi <= wave.phase_diff <= math.pi

    def test_two_channels_produce_two_waves(self):
        from rhythm_os.adapters.observe.synthetic_multi import SyntheticChannelSpec

        channels = [
            SyntheticChannelSpec(name="a", phase_offset_deg=0.0),
            SyntheticChannelSpec(name="b", phase_offset_deg=90.0),
        ]
        result = self._call(channels)
        assert len(result) == 2
        names = {w.channel for w in result}
        assert names == {"a", "b"}

    def test_noise_std_propagates(self):
        from rhythm_os.adapters.observe.synthetic_multi import SyntheticChannelSpec

        ch = SyntheticChannelSpec(name="noisy", phase_offset_deg=0.0, noise_std=0.1)
        result = self._call([ch])
        assert result[0].coherence is not None
        assert result[0].coherence < 1.0

    def test_zero_noise_coherence_is_one(self):
        from rhythm_os.adapters.observe.synthetic_multi import SyntheticChannelSpec

        ch = SyntheticChannelSpec(name="clean", phase_offset_deg=0.0, noise_std=0.0)
        result = self._call([ch])
        assert result[0].coherence == pytest.approx(1.0)


# ===========================================================================
# rhythm_os/core/coupling/coupling.py
# ===========================================================================


class TestComputeCoupling:
    def _df(self, data: dict):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")
        return pd.DataFrame(data)

    def test_returns_none_when_missing_col(self):
        from rhythm_os.core.coupling.coupling import compute_coupling

        df = self._df({"a": [1, 2, 3]})
        assert compute_coupling(df, "a", "missing") is None

    def test_returns_none_for_both_missing(self):
        from rhythm_os.core.coupling.coupling import compute_coupling

        df = self._df({"a": [1, 2, 3]})
        assert compute_coupling(df, "x", "y") is None

    def test_perfect_correlation(self):
        from rhythm_os.core.coupling.coupling import compute_coupling

        n = 30
        df = self._df({"x": list(range(n)), "y": list(range(n))})
        stat = compute_coupling(df, "x", "y", max_lag=2, min_points=5)
        assert stat is not None
        assert abs(stat.pearson) == pytest.approx(1.0, abs=1e-9)

    def test_inverse_correlation(self):
        from rhythm_os.core.coupling.coupling import compute_coupling

        n = 30
        df = self._df({"x": list(range(n)), "y": list(range(n, 0, -1))})
        stat = compute_coupling(df, "x", "y", max_lag=2, min_points=5)
        assert stat is not None
        assert stat.pearson < -0.9

    def test_weak_coupling_noted(self):
        from rhythm_os.core.coupling.coupling import compute_coupling
        import random

        random.seed(42)
        n = 30
        df = self._df(
            {
                "x": list(range(n)),
                "y": [random.gauss(0, 10) for _ in range(n)],
            }
        )
        stat = compute_coupling(
            df, "x", "y", max_lag=2, min_points=5, weak_abs_threshold=0.99
        )
        if stat is not None:
            assert stat.note == "weak coupling"

    def test_insufficient_points_returns_none(self):
        from rhythm_os.core.coupling.coupling import compute_coupling

        df = self._df({"x": [1.0, 2.0], "y": [1.0, 2.0]})
        # min_points=10 > 2 rows → None
        result = compute_coupling(df, "x", "y", max_lag=0, min_points=10)
        assert result is None

    def test_returns_coupling_stat_fields(self):
        from rhythm_os.core.coupling.coupling import compute_coupling, CouplingStat

        n = 30
        df = self._df({"x": list(range(n)), "y": list(range(n))})
        stat = compute_coupling(df, "x", "y", max_lag=2, min_points=5)
        assert stat is not None
        assert isinstance(stat, CouplingStat)
        assert stat.col == "x"
        assert stat.n >= 5


# ===========================================================================
# domain_to_* ingress adapters — all follow the same pattern
# ===========================================================================


def _ingress_decision_mock():
    d = MagicMock()
    d.gate_result = MagicMock()
    return d


def _run_ingress_main(module_name: str, domain: str, **dw_overrides):
    """
    Run the main() function of a domain_to_*_ingress module with mocked I/O.
    Returns the number of packets emitted.
    """
    import importlib

    mod = importlib.import_module(f"psr_tools.{module_name}")
    dw = _dw(domain=domain, **dw_overrides)
    decision = _ingress_decision_mock()

    with (
        patch(f"psr_tools.{module_name}.read_today", return_value=[dw]),
        patch(f"psr_tools.{module_name}.hydro_ingress_gate", return_value=decision),
        patch(f"psr_tools.{module_name}.enqueue_if_admitted") as mock_enqueue,
    ):
        mod.main()
        return mock_enqueue.call_count


def _run_ingress_main_empty(module_name: str):
    """Run with no waves (early return)."""
    import importlib

    mod = importlib.import_module(f"psr_tools.{module_name}")
    with patch(f"psr_tools.{module_name}.read_today", return_value=[]):
        mod.main()  # should return early without raising


class TestDomainToCyberIngress:
    def test_emits_packet_for_cyber_domain(self):
        count = _run_ingress_main("domain_to_cyber_ingress", "cyber")
        assert count == 1

    def test_skips_non_cyber_domain(self):
        count = _run_ingress_main("domain_to_cyber_ingress", "market")
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_cyber_ingress")


class TestDomainToMarketIngress:
    def test_emits_packet_for_market_domain(self):
        count = _run_ingress_main("domain_to_market_ingress", "market")
        assert count == 1

    def test_skips_non_market_domain(self):
        count = _run_ingress_main("domain_to_market_ingress", "cyber")
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_market_ingress")


class TestDomainToNaturalIngress:
    def test_emits_packet_for_natural_domain(self):
        count = _run_ingress_main("domain_to_natural_ingress", "natural")
        assert count == 1

    def test_skips_non_natural_domain(self):
        count = _run_ingress_main("domain_to_natural_ingress", "cyber")
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_natural_ingress")


class TestDomainToSystemIngress:
    def test_emits_packet_for_system_domain(self):
        count = _run_ingress_main(
            "domain_to_system_ingress", "system", channel="net_pressure"
        )
        assert count == 1

    def test_skips_non_system_domain(self):
        count = _run_ingress_main(
            "domain_to_system_ingress", "market", channel="net_pressure"
        )
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_system_ingress")


class TestDomainToTraffickingIngress:
    def test_emits_packet_for_trafficking_domain(self):
        count = _run_ingress_main("domain_to_trafficking_ingress", "human_trafficking")
        assert count == 1

    def test_skips_non_trafficking_domain(self):
        count = _run_ingress_main("domain_to_trafficking_ingress", "cyber")
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_trafficking_ingress")


class TestDomainToCyberAttackIngress:
    def test_emits_packet_for_cyber_attack_domain(self):
        count = _run_ingress_main(
            "domain_to_cyber_attack_ingress", "cyber", channel="attack_pressure"
        )
        assert count == 1

    def test_skips_wrong_channel(self):
        count = _run_ingress_main(
            "domain_to_cyber_attack_ingress", "cyber", channel="other"
        )
        assert count == 0

    def test_skips_non_cyber_domain(self):
        count = _run_ingress_main(
            "domain_to_cyber_attack_ingress", "market", channel="attack_pressure"
        )
        assert count == 0

    def test_empty_waves_no_emit(self):
        _run_ingress_main_empty("domain_to_cyber_attack_ingress")
