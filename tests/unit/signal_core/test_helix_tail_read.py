"""
Tests for helix_dashboard._tail_read_jsonl

Invariants:
- Returns empty list for non-existent file
- Returns all records when file is small (< tail_bytes)
- Returns only records from last tail_bytes when file is large
- Discards partial first line when seeking mid-file
- Skips malformed JSON lines without raising
- Works correctly with empty file
- Works correctly when file has only one record
- Returns records in file order (oldest to newest within the tail window)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_core.core.dashboard.helix_dashboard import _tail_read_jsonl


def _write_jsonl(path: Path, records: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestTailReadJsonl:
    def test_missing_file_returns_empty(self, tmp_path):
        result = _tail_read_jsonl(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        result = _tail_read_jsonl(p)
        assert result == []

    def test_single_record(self, tmp_path):
        p = tmp_path / "data.jsonl"
        _write_jsonl(p, [{"id": 1, "val": "x"}])
        result = _tail_read_jsonl(p)
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_small_file_returns_all(self, tmp_path):
        p = tmp_path / "data.jsonl"
        records = [{"n": i} for i in range(10)]
        _write_jsonl(p, records)
        result = _tail_read_jsonl(p, tail_bytes=131072)
        assert len(result) == 10
        assert result[0]["n"] == 0
        assert result[-1]["n"] == 9

    def test_large_file_returns_only_tail(self, tmp_path):
        p = tmp_path / "data.jsonl"
        # Write 200 records; each line is ~30 bytes → total ~6000 bytes
        # Use tail_bytes=500 so we only get the last ~16 records
        records = [{"seq": i, "pad": "x" * 10} for i in range(200)]
        _write_jsonl(p, records)
        result = _tail_read_jsonl(p, tail_bytes=500)
        # Should not return all 200 records
        assert len(result) < 200
        # Should return records from the end (highest seq numbers)
        seqs = [r["seq"] for r in result]
        assert 199 in seqs
        assert 0 not in seqs

    def test_malformed_lines_skipped(self, tmp_path):
        p = tmp_path / "data.jsonl"
        with p.open("w") as f:
            f.write('{"ok": 1}\n')
            f.write("NOT JSON\n")
            f.write('{"ok": 2}\n')
        result = _tail_read_jsonl(p)
        assert len(result) == 2
        assert result[0]["ok"] == 1
        assert result[1]["ok"] == 2

    def test_blank_lines_skipped(self, tmp_path):
        p = tmp_path / "data.jsonl"
        with p.open("w") as f:
            f.write('{"a": 1}\n')
            f.write("\n")
            f.write("   \n")
            f.write('{"a": 2}\n')
        result = _tail_read_jsonl(p)
        assert len(result) == 2

    def test_order_preserved_in_tail(self, tmp_path):
        p = tmp_path / "data.jsonl"
        records = [{"seq": i} for i in range(50)]
        _write_jsonl(p, records)
        result = _tail_read_jsonl(p, tail_bytes=200)
        seqs = [r["seq"] for r in result]
        assert seqs == sorted(seqs)

    def test_custom_tail_bytes_parameter(self, tmp_path):
        p = tmp_path / "data.jsonl"
        records = [{"seq": i, "pad": "." * 20} for i in range(100)]
        _write_jsonl(p, records)
        result_small = _tail_read_jsonl(p, tail_bytes=100)
        result_large = _tail_read_jsonl(p, tail_bytes=100000)
        assert len(result_small) < len(result_large)
