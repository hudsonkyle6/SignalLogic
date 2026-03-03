"""
Tests for rhythm_os.scope.adapters.dark_field_loader

Modules covered:
- load_penstock     (yields DarkFieldWaveView from penstock directory)
- _load_file        (reads JSONL file and yields projections)
- _project_wave     (projects a dict record to DarkFieldWaveView)
- DarkFieldWaveView (dataclass)

Invariants:
- load_penstock returns empty iterator when dir does not exist
- load_penstock reads all *.jsonl files in the directory
- _load_file skips blank lines
- _load_file skips malformed JSON lines
- _project_wave handles missing fields with safe defaults
- _project_wave parses ISO timestamp strings
- _project_wave handles non-string timestamp with t=0.0
- _project_wave handles missing afterglow_decay (None)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhythm_os.scope.adapters.dark_field_loader import (
    load_penstock,
    _load_file,
    _project_wave,
    DarkFieldWaveView,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, records: list) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _base_record(**overrides) -> dict:
    defaults = {
        "timestamp": "2024-01-15T12:00:00+00:00",
        "phase": 0.5,
        "amplitude": 0.7,
        "afterglow_decay": 0.6,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# load_penstock
# ---------------------------------------------------------------------------


class TestLoadPenstock:
    def test_nonexistent_dir_returns_empty(self, tmp_path):
        result = list(load_penstock(tmp_path / "nonexistent"))
        assert result == []

    def test_empty_dir_returns_empty(self, tmp_path):
        penstock = tmp_path / "penstock"
        penstock.mkdir()
        result = list(load_penstock(penstock))
        assert result == []

    def test_single_record_file_yields_one_view(self, tmp_path):
        penstock = tmp_path / "penstock"
        penstock.mkdir()
        _write_jsonl(penstock / "2024-01-15.jsonl", [_base_record()])
        result = list(load_penstock(penstock))
        assert len(result) == 1
        assert isinstance(result[0], DarkFieldWaveView)

    def test_multiple_records_yield_multiple_views(self, tmp_path):
        penstock = tmp_path / "penstock"
        penstock.mkdir()
        _write_jsonl(
            penstock / "2024-01-15.jsonl", [_base_record(), _base_record(amplitude=0.3)]
        )
        result = list(load_penstock(penstock))
        assert len(result) == 2

    def test_multiple_files_all_loaded(self, tmp_path):
        penstock = tmp_path / "penstock"
        penstock.mkdir()
        _write_jsonl(penstock / "2024-01-14.jsonl", [_base_record()])
        _write_jsonl(penstock / "2024-01-15.jsonl", [_base_record()])
        result = list(load_penstock(penstock))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _load_file
# ---------------------------------------------------------------------------


class TestLoadFile:
    def test_valid_record_yielded(self, tmp_path):
        p = tmp_path / "test.jsonl"
        _write_jsonl(p, [_base_record()])
        result = list(_load_file(p))
        assert len(result) == 1

    def test_blank_lines_skipped(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text("\n\n" + json.dumps(_base_record()) + "\n\n", encoding="utf-8")
        result = list(_load_file(p))
        assert len(result) == 1

    def test_malformed_json_skipped(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text(
            "not valid json\n" + json.dumps(_base_record()) + "\n", encoding="utf-8"
        )
        result = list(_load_file(p))
        assert len(result) == 1

    def test_multiple_records(self, tmp_path):
        p = tmp_path / "test.jsonl"
        _write_jsonl(p, [_base_record(), _base_record(amplitude=0.2)])
        result = list(_load_file(p))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _project_wave
# ---------------------------------------------------------------------------


class TestProjectWave:
    def test_iso_timestamp_parsed(self):
        record = _base_record(timestamp="2024-01-15T12:00:00+00:00")
        view = _project_wave(record)
        assert view.t > 0.0

    def test_non_string_timestamp_gives_zero(self):
        record = _base_record(timestamp=None)
        view = _project_wave(record)
        assert view.t == 0.0

    def test_bad_iso_timestamp_gives_zero(self):
        record = _base_record(timestamp="not-a-date")
        view = _project_wave(record)
        assert view.t == 0.0

    def test_amplitude_read(self):
        record = _base_record(amplitude=0.42)
        view = _project_wave(record)
        assert view.amplitude == pytest.approx(0.42)

    def test_phase_spread_read(self):
        record = _base_record(phase=0.33)
        view = _project_wave(record)
        assert view.phase_spread == pytest.approx(0.33)

    def test_afterglow_read(self):
        record = _base_record(afterglow_decay=0.75)
        view = _project_wave(record)
        assert view.afterglow == pytest.approx(0.75)

    def test_missing_afterglow_is_none(self):
        record = {k: v for k, v in _base_record().items() if k != "afterglow_decay"}
        view = _project_wave(record)
        assert view.afterglow is None

    def test_missing_amplitude_defaults_to_zero(self):
        record = {k: v for k, v in _base_record().items() if k != "amplitude"}
        view = _project_wave(record)
        assert view.amplitude == pytest.approx(0.0)

    def test_returns_dark_field_wave_view(self):
        view = _project_wave(_base_record())
        assert isinstance(view, DarkFieldWaveView)

    def test_buffer_margin_is_one(self):
        view = _project_wave(_base_record())
        assert view.buffer_margin == pytest.approx(1.0)

    def test_persistence_is_one(self):
        view = _project_wave(_base_record())
        assert view.persistence == 1
