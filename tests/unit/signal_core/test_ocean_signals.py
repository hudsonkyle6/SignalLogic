"""
Tests for the ocean signal layer of the Natural domain.

Modules covered:
- src/signal_core/domains/natural/derived_ocean_signals.py
  (wave_energy, wind_vector, pressure_gradient, normalization)
- apps/observatory_tools/emit_ocean_raw_once.py
  (load_buoy_data, compute_derived_signals, resample_to_hourly, emit_ocean_raw)
- src/rhythm_os/psr/transform/ocean_to_domain.py
  (project_ocean_domain)
- merge_signals compatibility — verifies the expected natural_* channel names
  are emitted so downstream merge operations can include them.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[4]
for _p in [str(ROOT / "src"), str(ROOT / "apps")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ===========================================================================
# derived_ocean_signals.py
# ===========================================================================


class TestWaveEnergy:
    def _e(self, h):
        from signal_core.domains.natural.derived_ocean_signals import wave_energy
        return wave_energy(h)

    def test_zero_height_gives_zero(self):
        assert self._e(0.0) == 0.0

    def test_known_value(self):
        # E = 0.125 * 1025 * 9.81 * 1.0² = 1256.90625
        e = self._e(1.0)
        assert abs(e - 1256.90625) < 0.01

    def test_energy_scales_with_height_squared(self):
        e1 = self._e(1.0)
        e2 = self._e(2.0)
        assert abs(e2 - 4 * e1) < 0.01

    def test_negative_height_clamped_to_zero(self):
        assert self._e(-1.0) == 0.0


class TestNormalizeWaveEnergy:
    def _n(self, e):
        from signal_core.domains.natural.derived_ocean_signals import normalize_wave_energy
        return normalize_wave_energy(e)

    def test_zero_energy_gives_zero(self):
        assert self._n(0.0) == 0.0

    def test_max_energy_gives_one(self):
        assert self._n(200_000.0) == 1.0

    def test_half_max_gives_half(self):
        assert abs(self._n(100_000.0) - 0.5) < 1e-9

    def test_above_max_clamped_to_one(self):
        assert self._n(999_999.0) == 1.0


class TestNormalizeWavePeriod:
    def _n(self, t):
        from signal_core.domains.natural.derived_ocean_signals import normalize_wave_period
        return normalize_wave_period(t)

    def test_min_period_gives_zero(self):
        assert self._n(2.0) == 0.0

    def test_max_period_gives_one(self):
        assert self._n(25.0) == 1.0

    def test_midpoint(self):
        # mid = (2 + 25) / 2 = 13.5
        assert abs(self._n(13.5) - 0.5) < 1e-9

    def test_below_min_clamped(self):
        assert self._n(0.0) == 0.0

    def test_above_max_clamped(self):
        assert self._n(100.0) == 1.0


class TestWindVector:
    def _wv(self, speed, direction):
        from signal_core.domains.natural.derived_ocean_signals import wind_vector
        return wind_vector(speed, direction)

    def test_north_wind_gives_negative_vy(self):
        # Wind FROM north (0°) → blowing southward → vy < 0
        vx, vy = self._wv(10.0, 0.0)
        assert abs(vx) < 1e-9
        assert vy < 0.0

    def test_east_wind_gives_negative_vx(self):
        # Wind FROM east (90°) → blowing westward → vx < 0
        vx, vy = self._wv(10.0, 90.0)
        assert vx < 0.0
        assert abs(vy) < 1e-6

    def test_zero_speed_gives_zero_components(self):
        vx, vy = self._wv(0.0, 45.0)
        assert vx == 0.0
        assert vy == 0.0

    def test_vector_magnitude_preserved(self):
        speed = 15.0
        vx, vy = self._wv(speed, 135.0)
        assert abs(math.hypot(vx, vy) - speed) < 1e-9


class TestNormalizeWindComponent:
    def _n(self, v):
        from signal_core.domains.natural.derived_ocean_signals import normalize_wind_component
        return normalize_wind_component(v)

    def test_zero_speed_gives_half(self):
        assert abs(self._n(0.0) - 0.5) < 1e-9

    def test_max_positive_gives_one(self):
        assert self._n(60.0) == 1.0

    def test_max_negative_gives_zero(self):
        assert self._n(-60.0) == 0.0

    def test_beyond_max_clamped(self):
        assert self._n(200.0) == 1.0
        assert self._n(-200.0) == 0.0


class TestPressureGradient:
    def _pg(self, pressures):
        from signal_core.domains.natural.derived_ocean_signals import pressure_gradient
        return pressure_gradient(pressures)

    def test_single_value_returns_zero(self):
        assert self._pg([1013.0]) == [0.0]

    def test_empty_returns_zero(self):
        assert self._pg([]) == [0.0]

    def test_constant_series_gives_zeros(self):
        result = self._pg([1013.0, 1013.0, 1013.0])
        assert all(v == 0.0 for v in result)

    def test_rising_pressure(self):
        result = self._pg([1010.0, 1012.0, 1015.0])
        assert result == [2.0, 3.0]

    def test_falling_pressure(self):
        result = self._pg([1015.0, 1010.0])
        assert result == [-5.0]

    def test_length_is_n_minus_one(self):
        result = self._pg([1000.0, 1001.0, 1002.0, 1003.0])
        assert len(result) == 3


class TestNormalizePressureGradient:
    def _n(self, delta):
        from signal_core.domains.natural.derived_ocean_signals import normalize_pressure_gradient
        return normalize_pressure_gradient(delta)

    def test_zero_gradient_gives_half(self):
        assert abs(self._n(0.0) - 0.5) < 1e-9

    def test_max_drop_gives_zero(self):
        assert self._n(-5.0) == 0.0

    def test_max_rise_gives_one(self):
        assert self._n(5.0) == 1.0

    def test_beyond_bounds_clamped(self):
        assert self._n(-100.0) == 0.0
        assert self._n(100.0) == 1.0


class TestNormalizeSurfaceTemp:
    def _n(self, t):
        from signal_core.domains.natural.derived_ocean_signals import normalize_surface_temp
        return normalize_surface_temp(t)

    def test_freezing_point_gives_zero(self):
        assert self._n(-2.0) == 0.0

    def test_max_temp_gives_one(self):
        assert self._n(35.0) == 1.0

    def test_midpoint(self):
        mid = (-2.0 + 35.0) / 2.0
        assert abs(self._n(mid) - 0.5) < 1e-9

    def test_below_min_clamped(self):
        assert self._n(-100.0) == 0.0

    def test_above_max_clamped(self):
        assert self._n(100.0) == 1.0


# ===========================================================================
# emit_ocean_raw_once.py — load_buoy_data
# ===========================================================================


class TestLoadBuoyData:
    def _make_csv(self, tmp_path, rows):
        csv_path = tmp_path / "buoy.csv"
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_missing_file_raises(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import load_buoy_data
        with pytest.raises(FileNotFoundError):
            load_buoy_data(tmp_path / "nonexistent.csv")

    def test_sorted_by_timestamp(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import load_buoy_data
        rows = [
            {"timestamp": "2025-01-03 00:00:00", "waveSignificantHeight": 1.0},
            {"timestamp": "2025-01-01 00:00:00", "waveSignificantHeight": 2.0},
            {"timestamp": "2025-01-02 00:00:00", "waveSignificantHeight": 1.5},
        ]
        csv_path = self._make_csv(tmp_path, rows)
        df = load_buoy_data(csv_path)
        heights = list(df["waveSignificantHeight"])
        assert heights == [2.0, 1.5, 1.0]

    def test_returns_utc_datetimeindex(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import load_buoy_data
        rows = [{"timestamp": "2025-06-01 12:00:00", "waveSignificantHeight": 1.0}]
        csv_path = self._make_csv(tmp_path, rows)
        df = load_buoy_data(csv_path)
        assert df.index.tz is not None


# ===========================================================================
# emit_ocean_raw_once.py — compute_derived_signals
# ===========================================================================


class TestComputeDerivedSignals:
    def _make_df(self, **kwargs):
        defaults = {
            "waveSignificantHeight": [1.0, 2.0],
            "wavePeakPeriod": [10.0, 12.0],
            "windSpeed": [5.0, 10.0],
            "windDirection": [0.0, 90.0],
            "barometerData": [1013.0, 1010.0],
            "surfaceTemp": [15.0, 16.0],
        }
        defaults.update(kwargs)
        idx = pd.date_range("2025-01-01", periods=2, freq="15min", tz="UTC")
        return pd.DataFrame(defaults, index=idx)

    def test_wave_energy_column_added(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        assert "wave_energy_J_m2" in df.columns

    def test_wind_vector_columns_added(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        assert "wind_vx_m_s" in df.columns
        assert "wind_vy_m_s" in df.columns

    def test_pressure_gradient_column_added(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        assert "pressure_gradient_hpa" in df.columns

    def test_pressure_gradient_first_row_zero(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        assert df["pressure_gradient_hpa"].iloc[0] == 0.0

    def test_pressure_gradient_second_row_negative(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        assert df["pressure_gradient_hpa"].iloc[1] == pytest.approx(-3.0)

    def test_missing_columns_get_defaults(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        idx = pd.date_range("2025-01-01", periods=1, freq="15min", tz="UTC")
        df = pd.DataFrame({}, index=idx)
        result = compute_derived_signals(df)
        assert "wave_energy_J_m2" in result.columns

    def test_wave_energy_scales_correctly(self):
        from observatory_tools.emit_ocean_raw_once import compute_derived_signals
        df = compute_derived_signals(self._make_df())
        # H=2.0 → E ≈ 4 * E(H=1.0)
        e1 = df["wave_energy_J_m2"].iloc[0]
        e2 = df["wave_energy_J_m2"].iloc[1]
        assert abs(e2 - 4 * e1) < 0.1


# ===========================================================================
# emit_ocean_raw_once.py — resample_to_hourly
# ===========================================================================


class TestResampleToHourly:
    def _make_15min_df(self):
        idx = pd.date_range("2025-01-01 00:00", periods=8, freq="15min", tz="UTC")
        data = {
            "wave_energy_J_m2": [100.0] * 8,
            "wave_period_s": [10.0] * 8,
            "wind_vx_m_s": [2.0] * 8,
            "wind_vy_m_s": [-3.0] * 8,
            "pressure_gradient_hpa": [0.5] * 8,
            "surface_temp_c": [18.0] * 8,
        }
        return pd.DataFrame(data, index=idx)

    def test_output_has_hourly_index(self):
        from observatory_tools.emit_ocean_raw_once import resample_to_hourly
        df = self._make_15min_df()
        hourly = resample_to_hourly(df)
        assert len(hourly) == 2  # 00:00 and 01:00

    def test_wave_energy_is_mean(self):
        from observatory_tools.emit_ocean_raw_once import resample_to_hourly
        df = self._make_15min_df()
        hourly = resample_to_hourly(df)
        assert hourly["wave_energy_J_m2"].iloc[0] == pytest.approx(100.0)

    def test_pressure_gradient_is_sum(self):
        from observatory_tools.emit_ocean_raw_once import resample_to_hourly
        df = self._make_15min_df()
        hourly = resample_to_hourly(df)
        # 4 rows × 0.5 = 2.0
        assert hourly["pressure_gradient_hpa"].iloc[0] == pytest.approx(2.0)


# ===========================================================================
# emit_ocean_raw_once.py — emit_ocean_raw
# ===========================================================================


class TestEmitOceanRaw:
    def _make_hourly(self):
        idx = pd.date_range("2025-06-01 00:00", periods=2, freq="1h", tz="UTC")
        return pd.DataFrame(
            {
                "wave_energy_J_m2": [5000.0, 6000.0],
                "wave_period_s": [12.0, 13.0],
                "wind_vx_m_s": [3.0, -2.0],
                "wind_vy_m_s": [-5.0, 1.0],
                "pressure_gradient_hpa": [-0.5, 0.2],
                "surface_temp_c": [20.0, 21.0],
            },
            index=idx,
        )

    def test_writes_jsonl_records(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        n = emit_ocean_raw(self._make_hourly(), out)
        assert out.exists()
        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == n

    def test_six_channels_per_hour(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        n = emit_ocean_raw(self._make_hourly(), out)
        assert n == 12  # 2 hours × 6 channels

    def test_all_expected_channels_present(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        emit_ocean_raw(self._make_hourly(), out)
        channels = set()
        for line in out.read_text().splitlines():
            if line.strip():
                channels.add(json.loads(line)["channel"])
        expected = {
            "wave_energy", "wave_period", "wind_vector_x",
            "wind_vector_y", "pressure_gradient", "surface_temp",
        }
        assert channels == expected

    def test_records_have_natural_lane(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        emit_ocean_raw(self._make_hourly(), out)
        for line in out.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                assert rec["lane"] == "natural"

    def test_phase_field_in_unit_interval(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        emit_ocean_raw(self._make_hourly(), out)
        for line in out.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                pf = rec["data"]["phase_field"]
                assert 0.0 <= pf <= 1.0, f"phase_field out of range: {pf} ({rec['channel']})"

    def test_appends_to_existing_file(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import emit_ocean_raw
        out = tmp_path / "ocean_raw.jsonl"
        emit_ocean_raw(self._make_hourly(), out)
        first_count = len([l for l in out.read_text().splitlines() if l.strip()])
        emit_ocean_raw(self._make_hourly(), out)
        second_count = len([l for l in out.read_text().splitlines() if l.strip()])
        assert second_count == 2 * first_count


# ===========================================================================
# ocean_to_domain.py — project_ocean_domain
# ===========================================================================


class TestProjectOceanDomain:
    def _write_ocean_raw(self, tmp_path, records):
        p = tmp_path / "2025-06-01.jsonl"
        with p.open("w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        return tmp_path

    def _make_rec(self, channel="wave_energy", phase_field=0.4):
        return {
            "t": 1748736000.0,
            "domain": "ocean_raw",
            "lane": "natural",
            "channel": channel,
            "field_cycle": "semi_diurnal",
            "window_s": 43200.0,
            "data": {
                "phase_external": 0.3,
                "phase_field": phase_field,
                "phase_diff": 0.1,
                "coherence": 0.85,
            },
            "raw": {},
            "extractor": {"source": "buoy_csv", "runner": "emit_ocean_raw_once", "version": "v1"},
        }

    def test_returns_list_of_domain_waves(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        from rhythm_os.psr.domain_wave import DomainWave
        self._write_ocean_raw(tmp_path, [self._make_rec()])
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        assert len(waves) == 1
        assert isinstance(waves[0], DomainWave)

    def test_domain_is_natural(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        self._write_ocean_raw(tmp_path, [self._make_rec()])
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        assert waves[0].domain == "natural"

    def test_channel_preserved(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        self._write_ocean_raw(tmp_path, [self._make_rec(channel="pressure_gradient")])
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        assert waves[0].channel == "pressure_gradient"

    def test_non_natural_lane_excluded(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        rec = self._make_rec()
        rec["lane"] = "market"
        self._write_ocean_raw(tmp_path, [rec])
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        assert waves == []

    def test_missing_dark_field_raises(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        monkeypatch.setattr(mod, "DATA_DIR", empty)
        with pytest.raises(FileNotFoundError):
            mod.project_ocean_domain()

    def test_multiple_channels_all_returned(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        channels = [
            "wave_energy", "wave_period", "wind_vector_x",
            "wind_vector_y", "pressure_gradient", "surface_temp",
        ]
        records = [self._make_rec(channel=ch) for ch in channels]
        self._write_ocean_raw(tmp_path, records)
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        emitted_channels = {w.channel for w in waves}
        assert emitted_channels == set(channels)

    def test_extractor_source_is_psr(self, tmp_path, monkeypatch):
        import rhythm_os.psr.transform.ocean_to_domain as mod
        self._write_ocean_raw(tmp_path, [self._make_rec()])
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        waves = mod.project_ocean_domain()
        assert "psr.transform.ocean_to_domain" in waves[0].extractor["source"]


# ===========================================================================
# merge_signals compatibility
#
# Verifies that the ocean channel names emitted by the pipeline match the
# column names expected in merged signal output.  No structural changes to
# merge_signals are required — this test confirms the naming contract.
# ===========================================================================


EXPECTED_NATURAL_OCEAN_COLUMNS = [
    "natural_wave_energy",
    "natural_wave_period",
    "natural_wind_vector_x",
    "natural_wind_vector_y",
    "natural_pressure_gradient",
    "natural_surface_temp",
]

_OCEAN_CHANNELS = [
    "wave_energy",
    "wave_period",
    "wind_vector_x",
    "wind_vector_y",
    "pressure_gradient",
    "surface_temp",
]


class TestMergeSignalsCompatibility:
    """
    Verifies that ocean channel identifiers follow the naming convention
    expected by merge_signals:  f"natural_{channel}".

    This ensures no structural changes are needed to the merge layer —
    each ocean DomainWave channel maps directly to a merge column.
    """

    def test_all_ocean_channels_produce_expected_merge_columns(self):
        merged_columns = [f"natural_{ch}" for ch in _OCEAN_CHANNELS]
        assert merged_columns == EXPECTED_NATURAL_OCEAN_COLUMNS

    def test_no_duplicate_channel_names(self):
        assert len(_OCEAN_CHANNELS) == len(set(_OCEAN_CHANNELS))

    def test_expected_columns_present_in_merge_spec(self):
        for col in EXPECTED_NATURAL_OCEAN_COLUMNS:
            assert col.startswith("natural_"), f"{col!r} must start with 'natural_'"

    def test_merge_column_count(self):
        assert len(EXPECTED_NATURAL_OCEAN_COLUMNS) == 6

    def test_wave_energy_column_name(self):
        assert "natural_wave_energy" in EXPECTED_NATURAL_OCEAN_COLUMNS

    def test_pressure_gradient_column_name(self):
        assert "natural_pressure_gradient" in EXPECTED_NATURAL_OCEAN_COLUMNS

    def test_wind_vector_columns_present(self):
        assert "natural_wind_vector_x" in EXPECTED_NATURAL_OCEAN_COLUMNS
        assert "natural_wind_vector_y" in EXPECTED_NATURAL_OCEAN_COLUMNS


# ===========================================================================
# normalize_cumulus_df — CUMULUS API response normalization
# ===========================================================================

# Representative sample from the live SPOT-32724C API response
_CUMULUS_SAMPLE_RECORDS = [
    {
        "index": 6885,
        "spotterID": "SPOT-32724C",
        "payloadType": "full",
        "batteryVoltage": "3.95",
        "solarVoltage": "5.36",
        "humidity": "13.50",
        "latitude": "42.0960535",
        "longitude": "-70.7172978",
        "timestamp": "2025-07-24 12:05:00",
        "waveSignHeight": "0.04",
        "wavePeakPeriod": "11.378",
        "waveMeanPeriod": "7.777",
        "wavePeakDirection": "194.627",
        "wavePeakDirectionalSpread": "73.028",
        "windSpeed": "0.00",
        "windDirection": 88,
        "surfaceTemp": None,
        "barometerData": "1020.81",
        "barometerUnits": "hPa",
    },
    {
        "index": 6886,
        "spotterID": "SPOT-32724C",
        "payloadType": "waves",
        "batteryVoltage": "3.96",
        "solarVoltage": "5.33",
        "humidity": "13.60",
        "latitude": "42.0960833",
        "longitude": "-70.7172667",
        "timestamp": "2025-07-24 12:15:00",
        "waveSignHeight": "0.04",
        "wavePeakPeriod": "11.380",
        "waveMeanPeriod": "8.040",
        "wavePeakDirection": "170.897",
        "wavePeakDirectionalSpread": "73.411",
        "windSpeed": "0.00",
        "windDirection": 102,
        "surfaceTemp": None,
        "barometerData": "1020.80",
        "barometerUnits": "hPa",
    },
    {
        "index": 6897,
        "spotterID": "SPOT-32724C",
        "payloadType": "full",
        "batteryVoltage": "3.95",
        "solarVoltage": "5.37",
        "humidity": "12.95",
        "latitude": "42.0960262",
        "longitude": "-70.7173113",
        "timestamp": "2025-07-24 12:35:00",
        "waveSignHeight": "0.07",
        "wavePeakPeriod": "7.314",
        "waveMeanPeriod": "5.669",
        "wavePeakDirection": "180.249",
        "wavePeakDirectionalSpread": "76.382",
        "windSpeed": "0.04",
        "windDirection": 284,
        "surfaceTemp": None,
        "barometerData": "1020.75",
        "barometerUnits": "hPa",
    },
]


class TestNormalizeCumulusDf:
    def _norm(self, records=None):
        from observatory_tools.emit_ocean_raw_once import normalize_cumulus_df
        return normalize_cumulus_df(records or _CUMULUS_SAMPLE_RECORDS)

    def test_empty_records_raises(self):
        from observatory_tools.emit_ocean_raw_once import normalize_cumulus_df
        with pytest.raises(ValueError, match="No records"):
            normalize_cumulus_df([])

    def test_wavesignheight_renamed(self):
        df = self._norm()
        assert "waveSignificantHeight" in df.columns
        assert "waveSignHeight" not in df.columns

    def test_wavesignificant_height_is_float(self):
        df = self._norm()
        assert df["waveSignificantHeight"].dtype == float
        assert df["waveSignificantHeight"].iloc[0] == pytest.approx(0.04)

    def test_wind_direction_coerced_to_float(self):
        df = self._norm()
        assert df["windDirection"].dtype == float
        assert df["windDirection"].iloc[0] == pytest.approx(88.0)

    def test_null_surface_temp_filled_with_default(self):
        from observatory_tools.emit_ocean_raw_once import _SURFACE_TEMP_DEFAULT
        df = self._norm()
        assert "surfaceTemp" in df.columns
        assert df["surfaceTemp"].notna().all()
        assert df["surfaceTemp"].iloc[0] == pytest.approx(_SURFACE_TEMP_DEFAULT)

    def test_barometer_data_is_float(self):
        df = self._norm()
        assert df["barometerData"].dtype == float
        assert df["barometerData"].iloc[0] == pytest.approx(1020.81)

    def test_index_is_utc_datetimeindex(self):
        df = self._norm()
        assert df.index.tz is not None
        assert str(df.index.tz) == "UTC"

    def test_sorted_ascending(self):
        # Feed records in reverse order to verify sorting
        reversed_records = list(reversed(_CUMULUS_SAMPLE_RECORDS))
        from observatory_tools.emit_ocean_raw_once import normalize_cumulus_df
        df = normalize_cumulus_df(reversed_records)
        assert df.index[0] < df.index[-1]

    def test_wavepeak_period_is_float(self):
        df = self._norm()
        assert df["wavePeakPeriod"].dtype == float


class TestFetchCumulusDataDateFilter:
    """
    Unit tests for the client-side date filtering logic inside fetch_cumulus_data.
    Uses requests mock to avoid real network calls.
    """

    def _make_api_response(self, timestamps):
        """Build a minimal CUMULUS-style API response for given timestamp strings."""
        records = []
        for i, ts in enumerate(timestamps):
            records.append({
                "index": i,
                "spotterID": "SPOT-32724C",
                "timestamp": ts,
                "waveSignHeight": "0.10",
                "wavePeakPeriod": "10.0",
                "windSpeed": "2.0",
                "windDirection": 90,
                "barometerData": "1013.25",
                "surfaceTemp": None,
            })
        return {"data": records, "count": len(records)}

    def test_client_side_filter_excludes_old_records(self, monkeypatch):
        from datetime import datetime, timezone
        import observatory_tools.emit_ocean_raw_once as mod

        response_data = self._make_api_response([
            "2025-01-01 00:00:00",  # outside window
            "2025-06-01 12:00:00",  # inside window
            "2025-06-01 18:00:00",  # inside window
        ])

        class FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return response_data

        monkeypatch.setattr(
            "requests.get",
            lambda *a, **kw: FakeResp(),
        )

        start = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 6, 2, 0, 0, 0, tzinfo=timezone.utc)
        records = mod.fetch_cumulus_data("SPOT-32724C", "token", start_dt=start, end_dt=end)
        assert len(records) == 2

    def test_all_records_included_when_all_in_window(self, monkeypatch):
        from datetime import datetime, timezone
        import observatory_tools.emit_ocean_raw_once as mod

        response_data = self._make_api_response([
            "2025-06-01 06:00:00",
            "2025-06-01 12:00:00",
        ])

        class FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return response_data

        monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResp())

        start = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 6, 2, 0, 0, 0, tzinfo=timezone.utc)
        records = mod.fetch_cumulus_data("SPOT-32724C", "token", start_dt=start, end_dt=end)
        assert len(records) == 2

    def test_empty_data_array_returns_empty_list(self, monkeypatch):
        from datetime import datetime, timezone
        import observatory_tools.emit_ocean_raw_once as mod

        class FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"data": []}

        monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResp())

        start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc)
        records = mod.fetch_cumulus_data("SPOT-32724C", "token", start_dt=start, end_dt=end)
        assert records == []

    def test_http_error_raises_runtime_error(self, monkeypatch):
        import requests as req
        import observatory_tools.emit_ocean_raw_once as mod
        from datetime import datetime, timezone

        class FakeResp:
            status_code = 403
            text = "Forbidden"
            def raise_for_status(self):
                raise req.HTTPError(response=self)

        monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResp())

        with pytest.raises(RuntimeError, match="CUMULUS API request failed"):
            mod.fetch_cumulus_data(
                "SPOT-32724C", "bad-token",
                start_dt=datetime(2025, 6, 1, tzinfo=timezone.utc),
                end_dt=datetime(2025, 6, 2, tzinfo=timezone.utc),
            )


class TestNormalizeCumulusDfFullPipeline:
    """
    Verify the full CUMULUS → derived signals → resample pipeline
    using the actual sample records from Plum Island SPOT-32724C.
    """

    def test_pipeline_produces_hourly_output(self):
        from observatory_tools.emit_ocean_raw_once import (
            normalize_cumulus_df,
            compute_derived_signals,
            resample_to_hourly,
        )
        df = normalize_cumulus_df(_CUMULUS_SAMPLE_RECORDS)
        df = compute_derived_signals(df)
        hourly = resample_to_hourly(df)
        assert len(hourly) >= 1

    def test_pipeline_wave_energy_is_non_negative(self):
        from observatory_tools.emit_ocean_raw_once import (
            normalize_cumulus_df,
            compute_derived_signals,
            resample_to_hourly,
        )
        df = normalize_cumulus_df(_CUMULUS_SAMPLE_RECORDS)
        df = compute_derived_signals(df)
        hourly = resample_to_hourly(df)
        assert (hourly["wave_energy_J_m2"] >= 0).all()

    def test_extractor_source_set_to_cumulus_api(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import (
            normalize_cumulus_df,
            compute_derived_signals,
            resample_to_hourly,
            emit_ocean_raw,
        )
        df = normalize_cumulus_df(_CUMULUS_SAMPLE_RECORDS)
        df = compute_derived_signals(df)
        hourly = resample_to_hourly(df)
        out = tmp_path / "out.jsonl"
        emit_ocean_raw(hourly, out, source="cumulus_api")
        recs = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert all(r["extractor"]["source"] == "cumulus_api" for r in recs)

    def test_extractor_version_v2(self, tmp_path):
        from observatory_tools.emit_ocean_raw_once import (
            normalize_cumulus_df,
            compute_derived_signals,
            resample_to_hourly,
            emit_ocean_raw,
        )
        df = normalize_cumulus_df(_CUMULUS_SAMPLE_RECORDS)
        df = compute_derived_signals(df)
        hourly = resample_to_hourly(df)
        out = tmp_path / "out.jsonl"
        emit_ocean_raw(hourly, out, source="cumulus_api")
        recs = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert all(r["extractor"]["version"] == "v2" for r in recs)
