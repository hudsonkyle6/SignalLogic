"""
Tests for rhythm_os.core.dark_field.store

Invariants:
- append_wave_from_hydro creates the JSONL file if it does not exist
- Each append adds exactly one line
- Multiple appends grow the file by exactly one line each
- Appended content is valid JSON containing the Wave's integrity_hash
- _daily_file returns correct path for a given date
- anchor_date defaults to the Wave's timestamp date
- anchor_date can be overridden explicitly
- Read-back of appended records is byte-identical to wave.to_json()
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from rhythm_os.core.wave.wave import Wave
from rhythm_os.core.dark_field.store import append_wave_from_hydro, _daily_file, PENSTOCK_DIR


FIXED_TS = "2025-06-01T00:00:00+00:00"
FIXED_DATE = date(2025, 6, 1)


def _wave(text: str = "test", ts: str = FIXED_TS) -> Wave:
    return Wave.create(
        text=text,
        signal_type="test",
        phase=0.5,
        frequency=1.0,
        amplitude=0.8,
        afterglow_decay=0.4,
        timestamp=ts,
    )


# ------------------------------------------------------------------
# _daily_file
# ------------------------------------------------------------------

class TestDailyFile:
    def test_returns_path_for_date(self):
        p = _daily_file(date(2025, 3, 15))
        assert p.name == "2025-03-15.jsonl"

    def test_parent_is_penstock_dir(self):
        p = _daily_file(date(2025, 3, 15))
        assert p.parent == PENSTOCK_DIR

    def test_different_dates_different_paths(self):
        p1 = _daily_file(date(2025, 1, 1))
        p2 = _daily_file(date(2025, 12, 31))
        assert p1 != p2


# ------------------------------------------------------------------
# append_wave_from_hydro — file creation and growth
# ------------------------------------------------------------------

class TestAppendWaveFromHydro:
    def test_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        assert path.exists()

    def test_returns_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        result = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        assert isinstance(result, Path)

    def test_single_append_one_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_three_appends_three_lines(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        for i in range(3):
            append_wave_from_hydro(_wave(text=f"w{i}"), anchor_date=FIXED_DATE)
        path = tmp_path / "2025-06-01.jsonl"
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_appended_line_is_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        line = path.read_text().strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_appended_record_contains_integrity_hash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        line = path.read_text().strip()
        parsed = json.loads(line)
        assert parsed["integrity_hash"] == w.integrity_hash

    def test_read_back_byte_identical(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        stored_line = path.read_text().rstrip("\n")
        assert stored_line == w.to_json()

    def test_anchor_date_from_wave_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave(ts="2025-09-20T08:00:00+00:00")
        path = append_wave_from_hydro(w)  # no anchor_date override
        assert path.name == "2025-09-20.jsonl"

    def test_explicit_anchor_date_overrides_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        w = _wave(ts="2025-09-20T08:00:00+00:00")
        path = append_wave_from_hydro(w, anchor_date=date(2025, 1, 1))
        assert path.name == "2025-01-01.jsonl"

    def test_bad_timestamp_falls_back_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", tmp_path
        )
        # Wave with an invalid timestamp string (from_json path bypass)
        w = Wave(
            signal_type="test",
            phase=0.0,
            frequency=1.0,
            amplitude=1.0,
            afterglow_decay=0.5,
            timestamp="not-a-timestamp",
            couplings={},
            text_content="x",
            integrity_hash="a" * 64,
        )
        # Should not raise; falls back to today
        path = append_wave_from_hydro(w)
        assert path.exists()

    def test_creates_parent_dirs_lazily(self, tmp_path, monkeypatch):
        nested = tmp_path / "sub" / "penstock"
        monkeypatch.setattr(
            "rhythm_os.core.dark_field.store.PENSTOCK_DIR", nested
        )
        w = _wave()
        path = append_wave_from_hydro(w, anchor_date=FIXED_DATE)
        assert path.exists()
