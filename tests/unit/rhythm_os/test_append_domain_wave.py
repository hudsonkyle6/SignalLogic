"""
Tests for rhythm_os.psr.append_domain_wave

Modules covered:
- append_domain_wave (append-only JSONL writer for DomainWaves)

Invariants:
- Raises FileNotFoundError when parent directory does not exist
- Raises ValueError when path exists but is not a regular file
- Appends valid JSON lines on success
- Multiple appends accumulate in the file
"""

from __future__ import annotations

import json

import pytest

from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.psr.domain_wave import DomainWave


_EXTRACTOR = {"method": "test"}


def _wave(t: float = 1000.0) -> DomainWave:
    return DomainWave(
        t=t,
        domain="test",
        channel="ch",
        field_cycle="diurnal",
        phase_external=0.0,
        phase_field=0.0,
        phase_diff=0.1,
        coherence=0.8,
        extractor=_EXTRACTOR,
    )


class TestAppendDomainWave:
    def test_raises_when_parent_missing(self, tmp_path):
        bad_path = tmp_path / "nonexistent_dir" / "file.jsonl"
        with pytest.raises(FileNotFoundError):
            append_domain_wave(bad_path, _wave())

    def test_raises_when_path_is_directory(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        with pytest.raises(ValueError):
            append_domain_wave(d, _wave())

    def test_creates_file_and_appends(self, tmp_path):
        path = tmp_path / "bus.jsonl"
        append_domain_wave(path, _wave())
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_appended_line_is_valid_json(self, tmp_path):
        path = tmp_path / "bus.jsonl"
        append_domain_wave(path, _wave())
        parsed = json.loads(path.read_text().strip())
        assert isinstance(parsed, dict)

    def test_appended_line_contains_domain(self, tmp_path):
        path = tmp_path / "bus.jsonl"
        append_domain_wave(path, _wave())
        parsed = json.loads(path.read_text().strip())
        assert parsed["domain"] == "test"

    def test_multiple_appends_accumulate(self, tmp_path):
        path = tmp_path / "bus.jsonl"
        for i in range(3):
            append_domain_wave(path, _wave(t=float(i)))
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3
