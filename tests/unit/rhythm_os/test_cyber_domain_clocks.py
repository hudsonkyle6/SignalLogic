"""
Tests for rhythm_os.core.domain_clocks.cyber

Invariants:
- CYBER_CYCLES is a non-empty dict mapping str → positive float
- Each key encodes its expected period in its name
- The six temporal bands are present and ordered from fastest to slowest
- No two bands share the same period
"""

from __future__ import annotations

from rhythm_os.core.domain_clocks.cyber import CYBER_CYCLES


class TestCyberCyclesPresence:
    def test_module_exports_cyber_cycles(self):
        assert CYBER_CYCLES is not None

    def test_six_bands_defined(self):
        assert len(CYBER_CYCLES) == 6

    def test_all_expected_bands_present(self):
        expected = {
            "burst_250ms",
            "burst_1s",
            "beat_5s",
            "minute_60s",
            "roll_15m",
            "session_1h",
        }
        assert set(CYBER_CYCLES.keys()) == expected


class TestCyberCyclesValues:
    def test_all_values_are_positive_floats(self):
        for name, period in CYBER_CYCLES.items():
            assert isinstance(period, float), f"{name} is not float"
            assert period > 0, f"{name} has non-positive period"

    def test_burst_250ms_is_quarter_second(self):
        assert CYBER_CYCLES["burst_250ms"] == 0.25

    def test_burst_1s_is_one_second(self):
        assert CYBER_CYCLES["burst_1s"] == 1.0

    def test_beat_5s_is_five_seconds(self):
        assert CYBER_CYCLES["beat_5s"] == 5.0

    def test_minute_60s_is_sixty_seconds(self):
        assert CYBER_CYCLES["minute_60s"] == 60.0

    def test_roll_15m_is_900_seconds(self):
        assert CYBER_CYCLES["roll_15m"] == 900.0

    def test_session_1h_is_3600_seconds(self):
        assert CYBER_CYCLES["session_1h"] == 3600.0

    def test_no_duplicate_periods(self):
        periods = list(CYBER_CYCLES.values())
        assert len(periods) == len(set(periods))


class TestCyberCyclesOrdering:
    def test_bands_span_from_sub_second_to_hourly(self):
        periods = list(CYBER_CYCLES.values())
        assert min(periods) < 1.0, "Expect at least one sub-second band"
        assert max(periods) >= 3600.0, "Expect at least one hourly band"

    def test_fastest_to_slowest_ratio(self):
        """Slowest band is at least 10,000x faster than the fastest."""
        mn = min(CYBER_CYCLES.values())
        mx = max(CYBER_CYCLES.values())
        assert mx / mn >= 10_000
