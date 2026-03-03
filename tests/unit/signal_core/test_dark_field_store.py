"""
Tests for signal_core.core.dark_field

Modules covered:
- compute_integrity_hash  (SHA-256 over canonical JSON)
- seal_record             (adds integrity_hash to a record)
- append_record           (append-only JSONL writer)
- _as_value               (dataclass → dict coercion)
- _utc_date_from_t        (timestamp → YYYY-MM-DD)

Invariants:
- compute_integrity_hash is deterministic
- seal_record raises if integrity_hash already present
- append_record creates missing directories
- append_record writes valid JSONL (each line is valid JSON)
- append_record seals records (adds integrity_hash)
- append_record raises if 't' missing and no filename_date provided
- _as_value returns asdict() for dataclasses, identity otherwise
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from signal_core.core.dark_field import (
    compute_integrity_hash,
    seal_record,
    append_record,
    _as_value,
    _utc_date_from_t,
)


# ---------------------------------------------------------------------------
# compute_integrity_hash
# ---------------------------------------------------------------------------


class TestComputeIntegrityHash:
    def test_returns_64_char_hex(self):
        h = compute_integrity_hash({"key": "value"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        record = {"a": 1, "b": "hello"}
        assert compute_integrity_hash(record) == compute_integrity_hash(record)

    def test_different_keys_different_hash(self):
        h1 = compute_integrity_hash({"a": 1})
        h2 = compute_integrity_hash({"b": 1})
        assert h1 != h2

    def test_different_values_different_hash(self):
        h1 = compute_integrity_hash({"a": 1})
        h2 = compute_integrity_hash({"a": 2})
        assert h1 != h2

    def test_key_order_independent(self):
        """Canonical JSON sorts keys — order should not matter."""
        h1 = compute_integrity_hash({"z": 1, "a": 2})
        h2 = compute_integrity_hash({"a": 2, "z": 1})
        assert h1 == h2


# ---------------------------------------------------------------------------
# seal_record
# ---------------------------------------------------------------------------


class TestSealRecord:
    def test_adds_integrity_hash(self):
        record = {"t": 1000.0, "value": "x"}
        sealed = seal_record(record)
        assert "integrity_hash" in sealed

    def test_does_not_mutate_original(self):
        record = {"t": 1000.0}
        seal_record(record)
        assert "integrity_hash" not in record

    def test_raises_if_already_sealed(self):
        record = {"t": 1000.0, "integrity_hash": "abc"}
        with pytest.raises(ValueError, match="integrity_hash"):
            seal_record(record)

    def test_sealed_hash_matches_compute(self):
        record = {"t": 1000.0, "v": 42}
        expected_hash = compute_integrity_hash(record)
        sealed = seal_record(record)
        assert sealed["integrity_hash"] == expected_hash

    def test_sealed_record_contains_original_keys(self):
        record = {"t": 1000.0, "domain": "test"}
        sealed = seal_record(record)
        assert sealed["t"] == 1000.0
        assert sealed["domain"] == "test"


# ---------------------------------------------------------------------------
# _utc_date_from_t
# ---------------------------------------------------------------------------


class TestUtcDateFromT:
    def test_returns_date_string(self):
        # Unix timestamp 0 = 1970-01-01 UTC
        result = _utc_date_from_t(0.0)
        assert result == "1970-01-01"

    def test_known_timestamp(self):
        # 2024-01-15 00:00:00 UTC = 1705276800
        result = _utc_date_from_t(1705276800.0)
        assert result == "2024-01-15"

    def test_format_is_yyyy_mm_dd(self):
        result = _utc_date_from_t(1000000.0)
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day


# ---------------------------------------------------------------------------
# append_record
# ---------------------------------------------------------------------------


class TestAppendRecord:
    def test_creates_file_on_first_write(self, tmp_path):
        record = {"t": 1705276800.0, "value": "hello"}
        path = append_record(record, base_dir=tmp_path)
        assert path.exists()

    def test_file_contains_valid_json_line(self, tmp_path):
        record = {"t": 1705276800.0, "value": "hello"}
        path = append_record(record, base_dir=tmp_path)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert isinstance(parsed, dict)

    def test_record_contains_integrity_hash(self, tmp_path):
        record = {"t": 1705276800.0, "v": 42}
        path = append_record(record, base_dir=tmp_path)
        parsed = json.loads(path.read_text().strip())
        assert "integrity_hash" in parsed

    def test_multiple_writes_append(self, tmp_path):
        for i in range(3):
            append_record({"t": 1705276800.0, "i": i}, base_dir=tmp_path)
        path = tmp_path / "2024-01-15.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        record = {"t": 1705276800.0, "x": 1}
        path = append_record(record, base_dir=nested)
        assert path.exists()

    def test_explicit_filename_date(self, tmp_path):
        record = {"t": 1705276800.0, "x": 1}
        path = append_record(record, base_dir=tmp_path, filename_date="2099-12-31")
        assert path.name == "2099-12-31.jsonl"

    def test_raises_without_t_and_no_filename_date(self, tmp_path):
        record = {"value": "no timestamp"}
        with pytest.raises(ValueError, match="'t'"):
            append_record(record, base_dir=tmp_path)

    def test_filename_derived_from_timestamp(self, tmp_path):
        # 2024-01-15 UTC
        record = {"t": 1705276800.0, "x": 1}
        path = append_record(record, base_dir=tmp_path)
        assert path.name == "2024-01-15.jsonl"


# ---------------------------------------------------------------------------
# _as_value
# ---------------------------------------------------------------------------


class TestAsValue:
    def test_non_dataclass_returned_as_is(self):
        assert _as_value("hello") == "hello"
        assert _as_value(42) == 42
        assert _as_value({"a": 1}) == {"a": 1}

    def test_dataclass_converted_to_dict(self):
        @dataclasses.dataclass
        class Simple:
            x: int
            y: str

        result = _as_value(Simple(x=1, y="hi"))
        assert isinstance(result, dict)
        assert result["x"] == 1
        assert result["y"] == "hi"
