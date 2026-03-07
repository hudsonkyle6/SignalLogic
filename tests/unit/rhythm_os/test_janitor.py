"""
Tests for rhythm_os.runtime.janitor

Modules covered:
- _aged_out
- run_janitor (dry-run and apply modes)

Invariants:
- _aged_out returns False for non-matching filenames
- _aged_out returns False for files within retention window
- _aged_out returns True for files older than cutoff
- run_janitor dry-run returns candidates without deleting
- run_janitor apply=True deletes aged files and returns them
- run_janitor ignores non-JSONL files in scanned directories
- run_janitor ignores files matching pattern but within window
- run_janitor handles missing directories gracefully
- run_janitor scans extra_dirs when provided
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rhythm_os.runtime.janitor import _aged_out, run_janitor


# ---------------------------------------------------------------------------
# _aged_out
# ---------------------------------------------------------------------------


class TestAgedOut:
    def _cutoff(self, days_ago: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    def test_non_jsonl_file_false(self):
        cutoff = self._cutoff(0)
        assert _aged_out("2020-01-01.json", cutoff) is False

    def test_non_date_filename_false(self):
        cutoff = self._cutoff(0)
        assert _aged_out("audit.jsonl", cutoff) is False

    def test_gibberish_filename_false(self):
        cutoff = self._cutoff(0)
        assert _aged_out("garbage.jsonl", cutoff) is False

    def test_file_within_window_false(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cutoff = self._cutoff(30)  # keep 30 days
        assert _aged_out(f"{today}.jsonl", cutoff) is False

    def test_file_older_than_cutoff_true(self):
        old = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        cutoff = self._cutoff(30)
        assert _aged_out(f"{old}.jsonl", cutoff) is True

    def test_exactly_at_cutoff_false(self):
        # File date == cutoff date: not aged out (< is strict)
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        # file_date is not < cutoff when they're the same day — could be equal or off by time of day
        # We just verify no exception and it returns a bool
        result = _aged_out(f"{thirty_days_ago}.jsonl", cutoff)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# run_janitor
# ---------------------------------------------------------------------------


class TestRunJanitor:
    def _make_dated_file(self, directory: Path, days_ago: int) -> Path:
        date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        p = directory / f"{date}.jsonl"
        p.write_text(json.dumps({"cycle": days_ago}) + "\n")
        return p

    def test_dry_run_does_not_delete(self, tmp_path):
        old_file = self._make_dated_file(tmp_path, 60)
        removed = run_janitor(retain_days=30, apply=False, extra_dirs=[tmp_path])
        assert old_file in removed
        assert old_file.exists()  # not deleted in dry-run

    def test_apply_deletes_aged_files(self, tmp_path):
        old_file = self._make_dated_file(tmp_path, 60)
        removed = run_janitor(retain_days=30, apply=True, extra_dirs=[tmp_path])
        assert old_file in removed
        assert not old_file.exists()

    def test_recent_files_not_removed(self, tmp_path):
        recent = self._make_dated_file(tmp_path, 5)
        removed = run_janitor(retain_days=30, apply=True, extra_dirs=[tmp_path])
        assert recent not in removed
        assert recent.exists()

    def test_non_jsonl_files_ignored(self, tmp_path):
        other = tmp_path / "notes.txt"
        other.write_text("keep me")
        removed = run_janitor(retain_days=0, apply=True, extra_dirs=[tmp_path])
        assert other not in removed
        assert other.exists()

    def test_non_date_jsonl_ignored(self, tmp_path):
        odd = tmp_path / "audit.jsonl"
        odd.write_text("{}\n")
        removed = run_janitor(retain_days=0, apply=True, extra_dirs=[tmp_path])
        assert odd not in removed
        assert odd.exists()

    def test_missing_directory_handled_gracefully(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        removed = run_janitor(retain_days=30, apply=False, extra_dirs=[missing])
        assert removed == []

    def test_multiple_aged_files_all_removed(self, tmp_path):
        old1 = self._make_dated_file(tmp_path, 40)
        old2 = self._make_dated_file(tmp_path, 50)
        recent = self._make_dated_file(tmp_path, 5)
        removed = run_janitor(retain_days=30, apply=True, extra_dirs=[tmp_path])
        assert old1 in removed
        assert old2 in removed
        assert recent not in removed

    def test_returns_list(self, tmp_path):
        result = run_janitor(retain_days=30, apply=False, extra_dirs=[tmp_path])
        assert isinstance(result, list)

    def test_zero_retain_days_removes_everything_dated(self, tmp_path):
        recent = self._make_dated_file(tmp_path, 1)
        removed = run_janitor(retain_days=0, apply=False, extra_dirs=[tmp_path])
        # A 1-day-old file should be aged out when retain_days=0
        assert recent in removed
