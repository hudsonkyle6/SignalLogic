"""
Tests for rhythm_os.psr.transform

Modules covered:
- natural_to_domain.py  (project_natural_domain, _latest_jsonl)
- market_to_domain.py   (project_market_domain — error path only)

Invariants:
- project_natural_domain returns a list of DomainWave objects
- Only records with lane=="natural" are included
- Records with missing required data fields are skipped (raise or are omitted)
- FileNotFoundError is raised when no JSONL exists in the data dir
- _latest_jsonl returns the lexicographically last .jsonl file
- Each DomainWave has correct domain="natural"
- project_market_domain raises FileNotFoundError when CSV is absent
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhythm_os.psr.transform.natural_to_domain import (
    project_natural_domain,
    _latest_jsonl,
)
from rhythm_os.psr.domain_wave import DomainWave


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _natural_record(**overrides) -> dict:
    """Build a minimal valid Natural Dark Field record."""
    base = {
        "t": 1705320000.0,
        "lane": "natural",
        "channel": "helix_projection",
        "field_cycle": "diurnal",
        "data": {
            "phase_external": 1.0,
            "phase_field": 0.5,
            "phase_diff": 0.5,
            "coherence": 0.8,
        },
    }
    base.update(overrides)
    return base


def _write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------
# _latest_jsonl
# ------------------------------------------------------------------


class TestLatestJsonl:
    def test_returns_last_file_alphabetically(self, tmp_path):
        for name in ("2025-01-01.jsonl", "2025-06-01.jsonl", "2025-03-01.jsonl"):
            (tmp_path / name).touch()
        result = _latest_jsonl(tmp_path)
        assert result.name == "2025-06-01.jsonl"

    def test_raises_file_not_found_when_empty(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _latest_jsonl(tmp_path)

    def test_single_file_returned(self, tmp_path):
        (tmp_path / "2025-01-01.jsonl").touch()
        result = _latest_jsonl(tmp_path)
        assert result.name == "2025-01-01.jsonl"


# ------------------------------------------------------------------
# project_natural_domain
# ------------------------------------------------------------------


class TestProjectNaturalDomain:
    def test_returns_list(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [_natural_record()])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert isinstance(result, list)

    def test_single_record_returns_one_wave(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [_natural_record()])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert len(result) == 1

    def test_returns_domain_wave_objects(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [_natural_record()])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert isinstance(result[0], DomainWave)

    def test_domain_is_natural(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [_natural_record()])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert result[0].domain == "natural"

    def test_non_natural_lane_excluded(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(
            p,
            [
                _natural_record(lane="natural"),
                _natural_record(lane="market"),
                _natural_record(lane="system"),
            ],
        )
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert len(result) == 1
        assert result[0].domain == "natural"

    def test_blank_lines_skipped(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as f:
            f.write("\n")
            f.write(json.dumps(_natural_record()) + "\n")
            f.write("   \n")
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert len(result) == 1

    def test_raises_when_no_data_dir_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        with pytest.raises(FileNotFoundError):
            project_natural_domain()

    def test_timestamp_preserved(self, tmp_path, monkeypatch):
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [_natural_record(t=1705320000.0)])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert result[0].t == pytest.approx(1705320000.0)

    def test_coherence_none_allowed(self, tmp_path, monkeypatch):
        rec = _natural_record()
        rec["data"]["coherence"] = None
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, [rec])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert result[0].coherence is None

    def test_multiple_natural_records_all_included(self, tmp_path, monkeypatch):
        recs = [_natural_record(t=1705320000.0 + i) for i in range(5)]
        p = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(p, recs)
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        assert len(result) == 5

    def test_reads_most_recent_file(self, tmp_path, monkeypatch):
        # Only the most recent JSONL should be read
        old = tmp_path / "2024-12-01.jsonl"
        new = tmp_path / "2025-01-15.jsonl"
        _write_jsonl(old, [_natural_record(t=1.0)])
        _write_jsonl(new, [_natural_record(t=2.0), _natural_record(t=3.0)])
        monkeypatch.setattr(
            "rhythm_os.psr.transform.natural_to_domain.DATA_DIR", tmp_path
        )
        result = project_natural_domain()
        # Should have 2 records from new file, not 1 from old
        assert len(result) == 2


# ------------------------------------------------------------------
# market_to_domain — skipped: pandas not installed in test environment
# ------------------------------------------------------------------
# project_market_domain raises FileNotFoundError when the CSV is absent,
# but we cannot import the module without pandas. The error-path contract
# is documented here; integration coverage requires a full environment.
