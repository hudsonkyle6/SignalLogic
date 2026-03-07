"""
Unit tests for observatory tool emitters.

Both modules make live external calls in production:
  - emit_market_raw_once: yfinance.download (17 tickers)
  - emit_natural_raw_once: requests.get (Open-Meteo), resolve_location (IP geo)

These tests mock all external I/O so CI never touches the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path and stub setup — must happen before importing modules under test
# ---------------------------------------------------------------------------

# observatory_tools scripts live directly in apps/observatory_tools/ (no package)
_OBS_DIR = Path(__file__).resolve().parents[3] / "apps" / "observatory_tools"
if str(_OBS_DIR) not in sys.path:
    sys.path.insert(0, str(_OBS_DIR))

# yfinance is not installed in the test environment; stub it before import
if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = MagicMock()

# ---------------------------------------------------------------------------
# Import modules under test
# ---------------------------------------------------------------------------

import emit_market_raw_once as market_mod
import emit_natural_raw_once as natural_mod


# ===========================================================================
# emit_market_raw_once
# ===========================================================================


class TestTickerConfig:
    """Regression-lock the ticker registry constants."""

    def test_ticker_names_not_empty(self):
        assert len(market_mod.TICKER_NAMES) > 0

    def test_required_tickers_present(self):
        # Core symbols for the 6 domain channels must not be silently removed
        required = {"^GSPC", "^VIX", "^TNX", "^IRX", "CL=F", "NG=F"}
        assert required.issubset(set(market_mod.TICKER_NAMES.keys()))

    def test_domain_pairs_keys(self):
        expected = {
            "volatility",
            "capital_cost",
            "energy",
            "maritime",
            "food",
            "materials",
        }
        assert set(market_mod._DOMAIN_PAIRS.keys()) == expected

    def test_domain_pair_symbols_are_in_ticker_names_values(self):
        all_names = set(market_mod.TICKER_NAMES.values())
        for domain, (ext, field) in market_mod._DOMAIN_PAIRS.items():
            assert ext in all_names, f"{domain}: '{ext}' not in TICKER_NAMES values"
            assert field in all_names, f"{domain}: '{field}' not in TICKER_NAMES values"


# ---------------------------------------------------------------------------
# Helpers that build fake yfinance DataFrames
# ---------------------------------------------------------------------------


def _make_yfinance_df(tickers: list[str], prices: list[float]) -> pd.DataFrame:
    """Multi-level column DataFrame matching yfinance output format."""
    data = {("Close", t): [prices[i]] for i, t in enumerate(tickers)}
    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


def _make_full_df() -> pd.DataFrame:
    """Return a valid DataFrame covering all 17 registered tickers."""
    tickers = list(market_mod.TICKER_NAMES.keys())
    prices = [100.0 + i for i in range(len(tickers))]
    return _make_yfinance_df(tickers, prices)


class TestMarketMainEmptyData:
    """yfinance returns empty DataFrame → sys.exit(0)."""

    def test_exits_on_empty_dataframe(self, tmp_path):
        empty_df = pd.DataFrame()
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=empty_df),
        ):
            with pytest.raises(SystemExit) as exc_info:
                market_mod.main()
            assert exc_info.value.code == 0

    def test_no_file_written_on_empty_data(self, tmp_path):
        empty_df = pd.DataFrame()
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=empty_df),
        ):
            try:
                market_mod.main()
            except SystemExit:
                pass
        assert list(tmp_path.glob("*.jsonl")) == []


class TestMarketMainNoValidSymbols:
    """All tickers return NaN → sys.exit(0)."""

    def test_exits_when_all_nan(self, tmp_path):

        tickers = list(market_mod.TICKER_NAMES.keys())
        nan_prices = [float("nan")] * len(tickers)
        nan_df = _make_yfinance_df(tickers, nan_prices)

        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=nan_df),
        ):
            with pytest.raises(SystemExit) as exc_info:
                market_mod.main()
            assert exc_info.value.code == 0

    def test_no_file_written_when_all_nan(self, tmp_path):

        tickers = list(market_mod.TICKER_NAMES.keys())
        nan_prices = [float("nan")] * len(tickers)
        nan_df = _make_yfinance_df(tickers, nan_prices)

        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=nan_df),
        ):
            try:
                market_mod.main()
            except SystemExit:
                pass
        assert list(tmp_path.glob("*.jsonl")) == []


class TestMarketMainSuccess:
    """Happy-path: yfinance returns valid data → file written with correct structure."""

    def _run(self, tmp_path) -> dict:
        full_df = _make_full_df()
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=full_df),
        ):
            market_mod.main()
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        line = files[0].read_text().strip()
        return json.loads(line)

    def test_record_written(self, tmp_path):
        record = self._run(tmp_path)
        assert record["domain"] == "market_raw"

    def test_record_lane(self, tmp_path):
        record = self._run(tmp_path)
        assert record["lane"] == "market"

    def test_record_has_t_timestamp(self, tmp_path):
        record = self._run(tmp_path)
        assert isinstance(record["t"], float)
        assert record["t"] > 0

    def test_record_has_symbols(self, tmp_path):
        record = self._run(tmp_path)
        assert "symbols" in record
        assert len(record["symbols"]) > 0

    def test_record_symbols_are_floats(self, tmp_path):
        record = self._run(tmp_path)
        for name, val in record["symbols"].items():
            assert isinstance(val, float), f"{name}: expected float, got {type(val)}"

    def test_extractor_source(self, tmp_path):
        record = self._run(tmp_path)
        assert record["extractor"]["source"] == "yfinance"
        assert record["extractor"]["runner"] == "emit_market_raw_once"
        assert record["extractor"]["version"] == "v3"

    def test_all_registered_ticker_names_present(self, tmp_path):
        record = self._run(tmp_path)
        expected_names = set(market_mod.TICKER_NAMES.values())
        assert expected_names.issubset(set(record["symbols"].keys()))

    def test_file_name_is_today_date(self, tmp_path):
        from datetime import datetime, timezone

        full_df = _make_full_df()
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=full_df),
        ):
            market_mod.main()
        today = datetime.now(timezone.utc).date().isoformat()
        expected = tmp_path / f"{today}.jsonl"
        assert expected.exists()

    def test_appends_on_second_call(self, tmp_path):
        full_df = _make_full_df()
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=full_df),
        ):
            market_mod.main()
            market_mod.main()
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        lines = [ln for ln in files[0].read_text().strip().splitlines() if ln]
        assert len(lines) == 2


class TestMarketPartialData:
    """Some tickers unavailable (missing from df) — graceful degradation."""

    def test_partial_symbols_still_emits(self, tmp_path):
        # Only 2 tickers present
        partial_df = _make_yfinance_df(["^GSPC", "^VIX"], [100.0, 20.0])
        with (
            patch.object(market_mod, "OUT_DIR", tmp_path),
            patch("yfinance.download", return_value=partial_df),
        ):
            market_mod.main()  # should not raise
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        record = json.loads(files[0].read_text().strip())
        assert "SP500" in record["symbols"]
        assert "VIX" in record["symbols"]


# ===========================================================================
# emit_natural_raw_once — pure helpers
# ===========================================================================


class TestClamp:
    def test_below_zero(self):
        assert natural_mod._clamp(-0.1) == 0.0

    def test_above_one(self):
        assert natural_mod._clamp(1.1) == 1.0

    def test_zero(self):
        assert natural_mod._clamp(0.0) == 0.0

    def test_one(self):
        assert natural_mod._clamp(1.0) == 1.0

    def test_midpoint(self):
        assert natural_mod._clamp(0.5) == 0.5

    def test_custom_bounds(self):
        assert natural_mod._clamp(5.0, lo=0.0, hi=10.0) == 5.0
        assert natural_mod._clamp(-1.0, lo=0.0, hi=10.0) == 0.0
        assert natural_mod._clamp(11.0, lo=0.0, hi=10.0) == 10.0


class TestCircularDiff:
    def test_zero_diff(self):
        assert natural_mod._circular_diff(0.3, 0.3) == pytest.approx(0.0)

    def test_positive_diff(self):
        result = natural_mod._circular_diff(0.4, 0.3)
        assert result == pytest.approx(0.1, abs=1e-9)

    def test_wraparound(self):
        # a=0.05, b=0.95 → shortest arc should be +0.1, not -0.9
        result = natural_mod._circular_diff(0.05, 0.95)
        assert result == pytest.approx(0.1, abs=1e-9)

    def test_negative_shortest_arc(self):
        # a=0.3, b=0.4 → shortest arc is -0.1
        result = natural_mod._circular_diff(0.3, 0.4)
        assert result == pytest.approx(-0.1, abs=1e-9)

    def test_result_in_range(self):
        import random

        rng = random.Random(42)
        for _ in range(100):
            a = rng.random()
            b = rng.random()
            d = natural_mod._circular_diff(a, b)
            assert -0.5 <= d <= 0.5, (
                f"_circular_diff({a}, {b}) = {d} out of [-0.5, 0.5]"
            )


class TestMakeRecord:
    def _rec(
        self,
        channel="helix_projection",
        phase_ext=0.25,
        phase_field=0.6,
        coherence=0.85,
        fetch_ok=True,
    ):
        return natural_mod._make_record(
            t=1700000000.0,
            channel=channel,
            phase_external=phase_ext,
            phase_field=phase_field,
            coherence=coherence,
            raw={"pressure_hpa": 1013.0},
            fetch_ok=fetch_ok,
            lat=40.0,
            lon=-74.0,
            label="TestCity",
        )

    def test_domain_is_natural_raw(self):
        assert self._rec()["domain"] == "natural_raw"

    def test_lane_is_natural(self):
        assert self._rec()["lane"] == "natural"

    def test_helix_projection_field_cycle(self):
        rec = self._rec(channel="helix_projection")
        assert rec["field_cycle"] == "semi_diurnal"

    def test_thermal_channel_field_cycle(self):
        rec = self._rec(channel="thermal")
        assert rec["field_cycle"] == "diurnal"

    def test_data_fields_present(self):
        rec = self._rec()
        assert "phase_external" in rec["data"]
        assert "phase_field" in rec["data"]
        assert "phase_diff" in rec["data"]
        assert "coherence" in rec["data"]

    def test_phase_diff_correctness(self):
        rec = self._rec(phase_ext=0.4, phase_field=0.3)
        expected_diff = natural_mod._circular_diff(0.4, 0.3)
        assert rec["data"]["phase_diff"] == pytest.approx(expected_diff)

    def test_extractor_meta(self):
        rec = natural_mod._make_record(
            t=1700000000.0,
            channel="helix_projection",
            phase_external=0.25,
            phase_field=0.6,
            coherence=0.85,
            raw={"pressure_hpa": 1013.0},
            fetch_ok=True,
            lat=51.5,
            lon=-0.1,
            label="London",
        )
        ext = rec["extractor"]
        assert ext["source"] == "open_meteo"
        assert ext["lat"] == 51.5
        assert ext["lon"] == -0.1
        assert ext["location_label"] == "London"
        assert ext["runner"] == "emit_natural_raw_once"
        assert ext["version"] == "v2"
        assert ext["fetch_ok"] is True

    def test_fetch_ok_false(self):
        rec = self._rec(fetch_ok=False)
        assert rec["extractor"]["fetch_ok"] is False

    def test_coherence_stored(self):
        rec = self._rec(coherence=0.42)
        assert rec["data"]["coherence"] == pytest.approx(0.42)

    def test_raw_payload_passed_through(self):
        rec = self._rec()
        assert rec["raw"]["pressure_hpa"] == 1013.0


# ===========================================================================
# emit_natural_raw_once — _fetch_weather
# ===========================================================================


class TestFetchWeather:
    def _mock_response(self, payload: dict, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        else:
            resp.raise_for_status.return_value = None
        return resp

    def test_success_returns_current_dict(self):
        payload = {"current": {"surface_pressure": 1010.0, "temperature_2m": 15.0}}
        with patch("requests.get", return_value=self._mock_response(payload)):
            result = natural_mod._fetch_weather(51.5, -0.1)
        assert result is not None
        assert result["surface_pressure"] == 1010.0

    def test_missing_current_key_returns_empty_dict(self):
        payload = {}  # no "current" key
        with patch("requests.get", return_value=self._mock_response(payload)):
            result = natural_mod._fetch_weather(51.5, -0.1)
        assert result == {}

    def test_http_error_returns_none(self):
        with patch(
            "requests.get", return_value=self._mock_response({}, status_code=500)
        ):
            result = natural_mod._fetch_weather(51.5, -0.1)
        assert result is None

    def test_network_exception_returns_none(self):
        with patch("requests.get", side_effect=ConnectionError("timeout")):
            result = natural_mod._fetch_weather(0.0, 0.0)
        assert result is None

    def test_passes_correct_params(self):
        payload = {"current": {}}
        mock_get = MagicMock(return_value=self._mock_response(payload))
        with patch("requests.get", mock_get):
            natural_mod._fetch_weather(40.7, -74.0)
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params["latitude"] == 40.7
        assert params["longitude"] == -74.0
        assert params["timezone"] == "UTC"


# ===========================================================================
# emit_natural_raw_once — main()
# ===========================================================================


def _weather_payload() -> dict:
    return {
        "surface_pressure": 1013.25,
        "temperature_2m": 20.0,
        "relative_humidity_2m": 55.0,
        "wind_speed_10m": 10.0,
        "wind_direction_10m": 180.0,
        "cloud_cover": 30.0,
        "weather_code": 1,
    }


def _run_natural_main(tmp_path, weather_data):
    """Run natural main() with mocked location, weather, and output dir."""
    mock_location = (51.5, -0.1, "TestCity")
    with (
        patch.object(natural_mod, "OUT_DIR", tmp_path),
        patch("emit_natural_raw_once.resolve_location", return_value=mock_location),
        patch("emit_natural_raw_once._fetch_weather", return_value=weather_data),
    ):
        natural_mod.main()


class TestNaturalMainSuccess:
    """Happy-path: weather fetch succeeds → 2 records written."""

    def _records(self, tmp_path) -> list[dict]:
        _run_natural_main(tmp_path, _weather_payload())
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        return [
            json.loads(ln) for ln in files[0].read_text().strip().splitlines() if ln
        ]

    def test_two_records_written(self, tmp_path):
        records = self._records(tmp_path)
        assert len(records) == 2

    def test_channels(self, tmp_path):
        records = self._records(tmp_path)
        channels = {r["channel"] for r in records}
        assert channels == {"helix_projection", "thermal"}

    def test_fetch_ok_true(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["extractor"]["fetch_ok"] is True

    def test_coherence_live(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["data"]["coherence"] == pytest.approx(0.85)

    def test_location_embedded(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["extractor"]["lat"] == 51.5
            assert r["extractor"]["lon"] == -0.1
            assert r["extractor"]["location_label"] == "TestCity"

    def test_domain_natural_raw(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["domain"] == "natural_raw"

    def test_raw_payload_present(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert "pressure_hpa" in r["raw"]
            assert "temperature_c" in r["raw"]

    def test_pressure_normalized_in_clamp_range(self, tmp_path):
        records = self._records(tmp_path)
        helix = next(r for r in records if r["channel"] == "helix_projection")
        assert 0.0 <= helix["data"]["phase_field"] <= 1.0

    def test_temperature_normalized_in_clamp_range(self, tmp_path):
        records = self._records(tmp_path)
        thermal = next(r for r in records if r["channel"] == "thermal")
        assert 0.0 <= thermal["data"]["phase_field"] <= 1.0

    def test_file_name_is_today(self, tmp_path):
        from datetime import datetime, timezone

        _run_natural_main(tmp_path, _weather_payload())
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert (tmp_path / f"{today}.jsonl").exists()

    def test_appends_on_second_call(self, tmp_path):
        _run_natural_main(tmp_path, _weather_payload())
        _run_natural_main(tmp_path, _weather_payload())
        files = list(tmp_path.glob("*.jsonl"))
        lines = [ln for ln in files[0].read_text().strip().splitlines() if ln]
        assert len(lines) == 4  # 2 records × 2 runs


class TestNaturalMainFetchFailed:
    """Weather fetch fails → stub mode: 2 records written with coherence=0.0."""

    def _records(self, tmp_path) -> list[dict]:
        _run_natural_main(tmp_path, None)  # None = fetch failed
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        return [
            json.loads(ln) for ln in files[0].read_text().strip().splitlines() if ln
        ]

    def test_still_writes_two_records(self, tmp_path):
        records = self._records(tmp_path)
        assert len(records) == 2

    def test_fetch_ok_false(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["extractor"]["fetch_ok"] is False

    def test_coherence_zero(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["data"]["coherence"] == pytest.approx(0.0)

    def test_pressure_stub_value(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["raw"]["pressure_hpa"] == pytest.approx(1013.25)

    def test_temperature_stub_value(self, tmp_path):
        records = self._records(tmp_path)
        for r in records:
            assert r["raw"]["temperature_c"] == pytest.approx(0.0)
