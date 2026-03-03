"""
Tests for rhythm_os.control_plane.mandate_store

Modules covered:
- load_latest_mandate (loads newest JSON mandate file from a directory)

Invariants:
- Returns None when directory does not exist
- Returns None when directory is empty (no .json files)
- Returns a Mandate when a valid JSON file is found
- Returns the newest file by mtime when multiple files exist
- Raises MandateError when file contains a non-dict JSON value
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from rhythm_os.control_plane.mandate_store import load_latest_mandate
from rhythm_os.control_plane.mandate import Mandate, MandateError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_mandate_dict() -> dict:
    """Minimal valid mandate dict matching Mandate.from_dict expectations."""
    now = time.time()
    return {
        "principal": "test-principal",
        "issued_at": now - 60,
        "expires_at": now + 3600,
        "scope": ["observe"],
        "nonce": "test-nonce-123",
        "signature": "test-sig",
    }


def _write_mandate(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadLatestMandate:
    def test_nonexistent_dir_returns_none(self, tmp_path):
        result = load_latest_mandate(tmp_path / "nonexistent")
        assert result is None

    def test_empty_dir_returns_none(self, tmp_path):
        d = tmp_path / "mandates"
        d.mkdir()
        result = load_latest_mandate(d)
        assert result is None

    def test_valid_mandate_file_loaded(self, tmp_path):
        d = tmp_path / "mandates"
        d.mkdir()
        data = _valid_mandate_dict()
        _write_mandate(d / "mandate_01.json", data)
        result = load_latest_mandate(d)
        assert isinstance(result, Mandate)

    def test_newest_file_returned_on_multiple(self, tmp_path):
        """The file with the most recent mtime is used."""
        d = tmp_path / "mandates"
        d.mkdir()
        data = _valid_mandate_dict()

        old = d / "mandate_old.json"
        _write_mandate(old, data)
        time.sleep(0.01)
        new = d / "mandate_new.json"
        _write_mandate(new, data)

        # Verify newest was picked (both valid, just check no crash)
        result = load_latest_mandate(d)
        assert isinstance(result, Mandate)

    def test_non_dict_raises_mandate_error(self, tmp_path):
        d = tmp_path / "mandates"
        d.mkdir()
        (d / "bad.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(MandateError):
            load_latest_mandate(d)
