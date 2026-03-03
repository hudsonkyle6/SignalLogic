"""
Tests for rhythm_os.runtime.readiness

Modules covered:
- ReadinessStatus.summary()
- _count_today_records()
- check_readiness()

Invariants:
- _count_today_records returns 0 when directory or file does not exist
- _count_today_records counts non-blank lines in today's JSONL
- check_readiness returns ReadinessStatus with correct booleans
- ReadinessStatus.summary() includes system and natural tier labels
- system_ready = True when system_count >= min_meter_cycles
- overall_ready = True only when both tiers are ready
"""

from __future__ import annotations

from datetime import datetime, timezone


from rhythm_os.runtime.readiness import (
    ReadinessStatus,
    _count_today_records,
    check_readiness,
)


# ---------------------------------------------------------------------------
# ReadinessStatus.summary
# ---------------------------------------------------------------------------


class TestReadinessStatusSummary:
    def _status(self, system_ready: bool, natural_ready: bool) -> ReadinessStatus:
        return ReadinessStatus(
            system_count=30 if system_ready else 5,
            natural_count=4 if natural_ready else 2,
            min_meter_cycles=30,
            min_natural_records=4,
            system_ready=system_ready,
            natural_ready=natural_ready,
            overall_ready=system_ready and natural_ready,
        )

    def test_both_warm_summary_contains_warm(self):
        s = self._status(True, True).summary()
        assert "WARM" in s

    def test_system_cold_shows_count(self):
        s = self._status(False, True).summary()
        assert "cold" in s or "5" in s

    def test_summary_contains_system_and_natural(self):
        s = self._status(True, False).summary()
        assert "system" in s
        assert "natural" in s


# ---------------------------------------------------------------------------
# _count_today_records
# ---------------------------------------------------------------------------


class TestCountTodayRecords:
    def test_missing_dir_returns_zero(self, tmp_path):
        result = _count_today_records(tmp_path / "nonexistent")
        assert result == 0

    def test_missing_file_returns_zero(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        result = _count_today_records(d)
        assert result == 0

    def test_counts_non_blank_lines(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        f = d / f"{today}.jsonl"
        f.write_text('{"a":1}\n{"b":2}\n\n{"c":3}\n', encoding="utf-8")
        assert _count_today_records(d) == 3

    def test_blank_lines_not_counted(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        f = d / f"{today}.jsonl"
        f.write_text("\n\n\n", encoding="utf-8")
        assert _count_today_records(d) == 0

    def test_empty_file_returns_zero(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (d / f"{today}.jsonl").write_text("", encoding="utf-8")
        assert _count_today_records(d) == 0


# ---------------------------------------------------------------------------
# check_readiness
# ---------------------------------------------------------------------------


class TestCheckReadiness:
    def _call(self, monkeypatch, system_count: int, natural_count: int, **kwargs):
        import rhythm_os.runtime.readiness as mod

        monkeypatch.setattr(
            mod,
            "_count_today_records",
            lambda d: system_count if "meter" in str(d) else natural_count,
        )
        return check_readiness(**kwargs)

    def test_returns_readiness_status(self, monkeypatch):
        result = self._call(monkeypatch, 30, 4)
        assert isinstance(result, ReadinessStatus)

    def test_both_ready_when_counts_meet_thresholds(self, monkeypatch):
        result = self._call(
            monkeypatch, 30, 4, min_meter_cycles=30, min_natural_records=4
        )
        assert result.system_ready is True
        assert result.natural_ready is True
        assert result.overall_ready is True

    def test_system_not_ready_below_threshold(self, monkeypatch):
        result = self._call(
            monkeypatch, 5, 10, min_meter_cycles=30, min_natural_records=4
        )
        assert result.system_ready is False
        assert result.overall_ready is False

    def test_natural_not_ready_below_threshold(self, monkeypatch):
        result = self._call(
            monkeypatch, 50, 2, min_meter_cycles=30, min_natural_records=4
        )
        assert result.natural_ready is False
        assert result.overall_ready is False

    def test_counts_returned_in_status(self, monkeypatch):
        result = self._call(monkeypatch, 15, 3)
        assert result.system_count == 15
        assert result.natural_count == 3

    def test_default_thresholds_used(self, monkeypatch):
        """Default min_meter_cycles=30, min_natural_records=4."""
        result = self._call(monkeypatch, 30, 4)
        assert result.min_meter_cycles == 30
        assert result.min_natural_records == 4
