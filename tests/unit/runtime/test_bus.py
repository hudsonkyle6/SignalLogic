"""
Tests for rhythm_os.runtime.bus

Covers:
  - today_bus_file: returns correct date-stamped path
  - load_recent_domain_waves: empty dir, missing dir, valid waves, time window filter,
    malformed lines skipped, sorted output
  - has_emission_at_time: missing dir, no match, exact match, partial match
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.runtime.bus import (
    has_emission_at_time,
    load_recent_domain_waves,
    today_bus_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wave(
    t: float = 1_700_000_000.0,
    domain: str = "weather",
    channel: str = "temperature",
) -> DomainWave:
    return DomainWave(
        t=t,
        domain=domain,
        channel=channel,
        field_cycle="computed",
        phase_external=0.1,
        phase_field=0.2,
        phase_diff=0.1,
        coherence=0.9,
        extractor={"source": "test"},
    )


def _write_wave(path: Path, wave: DomainWave) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(wave.to_json() + "\n")


# ---------------------------------------------------------------------------
# today_bus_file
# ---------------------------------------------------------------------------


class TestTodayBusFile:
    def test_returns_path_in_bus_dir(self, tmp_path):
        t_ref = 1_700_000_000.0
        result = today_bus_file(bus_dir=tmp_path, t_ref=t_ref)
        assert result.parent == tmp_path

    def test_filename_is_iso_date(self, tmp_path):
        t_ref = 1_700_000_000.0
        expected_date = time.strftime("%Y-%m-%d", time.localtime(t_ref))
        result = today_bus_file(bus_dir=tmp_path, t_ref=t_ref)
        assert result.name == f"{expected_date}.jsonl"

    def test_different_timestamps_same_day_same_file(self, tmp_path):
        # Find two timestamps on the same local day
        t_ref = 1_700_000_000.0
        date = time.strftime("%Y-%m-%d", time.localtime(t_ref))
        # midnight of the same day
        t2 = t_ref - (t_ref % 86400)
        date2 = time.strftime("%Y-%m-%d", time.localtime(t2))
        if date == date2:
            assert today_bus_file(bus_dir=tmp_path, t_ref=t_ref) == today_bus_file(
                bus_dir=tmp_path, t_ref=t2
            )


# ---------------------------------------------------------------------------
# load_recent_domain_waves
# ---------------------------------------------------------------------------


class TestLoadRecentDomainWaves:
    def test_missing_dir_returns_empty(self, tmp_path):
        result = load_recent_domain_waves(
            bus_dir=tmp_path / "nonexistent",
            t_ref=1_000.0,
            history_window_sec=3600.0,
        )
        assert result == []

    def test_empty_dir_returns_empty(self, tmp_path):
        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=1_000.0,
            history_window_sec=3600.0,
        )
        assert result == []

    def test_loads_wave_within_window(self, tmp_path):
        t_ref = 1_700_000_000.0
        wave = _make_wave(t=t_ref)
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        assert len(result) == 1
        assert result[0].domain == "weather"
        assert result[0].t == pytest.approx(t_ref)

    def test_excludes_wave_outside_window(self, tmp_path):
        t_ref = 1_700_000_000.0
        # Wave 2 hours outside window
        wave = _make_wave(t=t_ref - 7200.0)
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        assert result == []

    def test_malformed_json_lines_skipped(self, tmp_path):
        t_ref = 1_700_000_000.0
        bus_file = tmp_path / "2023-11-14.jsonl"
        # Write one bad line then one good wave
        with bus_file.open("w") as f:
            f.write("not valid json\n")
            f.write(_make_wave(t=t_ref).to_json() + "\n")

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        assert len(result) == 1

    def test_wave_missing_t_field_skipped(self, tmp_path):
        t_ref = 1_700_000_000.0
        bus_file = tmp_path / "2023-11-14.jsonl"
        bad_rec = {"domain": "x", "channel": "y"}
        with bus_file.open("w") as f:
            f.write(json.dumps(bad_rec) + "\n")
            f.write(_make_wave(t=t_ref).to_json() + "\n")

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        # Only the valid wave survives
        assert len(result) == 1

    def test_result_sorted_by_t(self, tmp_path):
        t_ref = 1_700_000_000.0
        bus_file = tmp_path / "2023-11-14.jsonl"
        for delta in [200.0, 50.0, 100.0]:
            _write_wave(bus_file, _make_wave(t=t_ref - delta))

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        ts = [w.t for w in result]
        assert ts == sorted(ts)

    def test_returns_domainwave_objects(self, tmp_path):
        t_ref = 1_700_000_000.0
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, _make_wave(t=t_ref))

        result = load_recent_domain_waves(
            bus_dir=tmp_path,
            t_ref=t_ref,
            history_window_sec=3600.0,
        )
        assert all(isinstance(w, DomainWave) for w in result)


# ---------------------------------------------------------------------------
# has_emission_at_time
# ---------------------------------------------------------------------------


class TestHasEmissionAtTime:
    def test_missing_dir_returns_false(self, tmp_path):
        assert (
            has_emission_at_time(
                bus_dir=tmp_path / "nonexistent",
                t_ref=1_000.0,
                domain="x",
                channel="y",
            )
            is False
        )

    def test_empty_dir_returns_false(self, tmp_path):
        assert (
            has_emission_at_time(
                bus_dir=tmp_path,
                t_ref=1_000.0,
                domain="x",
                channel="y",
            )
            is False
        )

    def test_exact_match_returns_true(self, tmp_path):
        t_ref = 1_700_000_000.0
        wave = _make_wave(t=t_ref, domain="weather", channel="temperature")
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        assert (
            has_emission_at_time(
                bus_dir=tmp_path,
                t_ref=t_ref,
                domain="weather",
                channel="temperature",
            )
            is True
        )

    def test_wrong_domain_returns_false(self, tmp_path):
        t_ref = 1_700_000_000.0
        wave = _make_wave(t=t_ref, domain="weather", channel="temperature")
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        assert (
            has_emission_at_time(
                bus_dir=tmp_path,
                t_ref=t_ref,
                domain="energy",
                channel="temperature",
            )
            is False
        )

    def test_wrong_channel_returns_false(self, tmp_path):
        t_ref = 1_700_000_000.0
        wave = _make_wave(t=t_ref, domain="weather", channel="temperature")
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        assert (
            has_emission_at_time(
                bus_dir=tmp_path,
                t_ref=t_ref,
                domain="weather",
                channel="pressure",
            )
            is False
        )

    def test_wrong_t_ref_returns_false(self, tmp_path):
        t_ref = 1_700_000_000.0
        wave = _make_wave(t=t_ref, domain="weather", channel="temperature")
        bus_file = tmp_path / "2023-11-14.jsonl"
        _write_wave(bus_file, wave)

        assert (
            has_emission_at_time(
                bus_dir=tmp_path,
                t_ref=t_ref + 1.0,
                domain="weather",
                channel="temperature",
            )
            is False
        )

    def test_malformed_lines_do_not_raise(self, tmp_path):
        bus_file = tmp_path / "2023-11-14.jsonl"
        with bus_file.open("w") as f:
            f.write("not json\n")
            f.write("{incomplete\n")

        # Should not raise, just return False
        result = has_emission_at_time(
            bus_dir=tmp_path,
            t_ref=1_000.0,
            domain="x",
            channel="y",
        )
        assert result is False
