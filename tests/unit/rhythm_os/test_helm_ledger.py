"""
Tests for rhythm_os.domain.helm.ledger

Covers append, load, n-limiting, malformed-line resilience,
and the record_from_helm_result helper.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhythm_os.domain.helm.engine import HelmResult
from rhythm_os.domain.helm.ledger import (
    HelmRecord,
    append_helm_record,
    load_helm_records,
    record_from_helm_result,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def helm_log(tmp_path, monkeypatch):
    """Redirect HELM_LOG_PATH to a temp file and return its Path."""
    log_path = tmp_path / "dark_field" / "helm" / "helm_log.jsonl"
    import rhythm_os.domain.helm.ledger as ledger_mod
    monkeypatch.setattr(ledger_mod, "HELM_LOG_PATH", log_path)
    return log_path


def _rec(state: str = "ACT", cycle_ts: float = 1.0) -> HelmRecord:
    return HelmRecord(
        state=state,
        rationale="test rationale",
        ts=1.0,
        cycle_ts=cycle_ts,
        admission_rate=0.80,
        anomaly_rate=0.02,
        strong_events=0,
        event_count=0,
        brittleness=0.1,
        strain=0.2,
    )


# ---------------------------------------------------------------------------
# record_from_helm_result
# ---------------------------------------------------------------------------


class TestRecordFromHelmResult:
    def test_state_transferred(self):
        h = HelmResult(state="WAIT", rationale="r", ts=5.0)
        rec = record_from_helm_result(h, cycle_ts=4.0)
        assert rec.state == "WAIT"

    def test_rationale_transferred(self):
        h = HelmResult(state="ACT", rationale="nominal", ts=5.0)
        rec = record_from_helm_result(h, cycle_ts=4.0)
        assert rec.rationale == "nominal"

    def test_cycle_ts_separate_from_ts(self):
        h = HelmResult(state="ACT", rationale="r", ts=99.0)
        rec = record_from_helm_result(h, cycle_ts=77.0)
        assert rec.ts == pytest.approx(99.0)
        assert rec.cycle_ts == pytest.approx(77.0)

    def test_metrics_transferred(self):
        h = HelmResult(
            state="PUSH", rationale="r", ts=1.0,
            admission_rate=0.92, anomaly_rate=0.0,
            strong_events=0, event_count=0,
            brittleness=0.1, strain=0.05,
        )
        rec = record_from_helm_result(h, cycle_ts=1.0)
        assert rec.admission_rate == pytest.approx(0.92)
        assert rec.brittleness == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# append_helm_record
# ---------------------------------------------------------------------------


class TestAppendHelmRecord:
    def test_creates_file(self, helm_log):
        assert not helm_log.exists()
        append_helm_record(_rec())
        assert helm_log.exists()

    def test_creates_parent_directories(self, helm_log):
        assert not helm_log.parent.exists()
        append_helm_record(_rec())
        assert helm_log.parent.is_dir()

    def test_writes_valid_json(self, helm_log):
        append_helm_record(_rec(state="WAIT"))
        line = helm_log.read_text().strip()
        data = json.loads(line)
        assert data["state"] == "WAIT"

    def test_appends_multiple_records(self, helm_log):
        append_helm_record(_rec(state="WAIT"))
        append_helm_record(_rec(state="ACT"))
        append_helm_record(_rec(state="PUSH"))
        lines = [l for l in helm_log.read_text().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_each_line_is_independent_json(self, helm_log):
        for s in ("WAIT", "PREPARE", "ACT", "PUSH"):
            append_helm_record(_rec(state=s))
        lines = helm_log.read_text().splitlines()
        states = [json.loads(l)["state"] for l in lines if l.strip()]
        assert states == ["WAIT", "PREPARE", "ACT", "PUSH"]


# ---------------------------------------------------------------------------
# load_helm_records
# ---------------------------------------------------------------------------


class TestLoadHelmRecords:
    def test_empty_list_when_file_absent(self, helm_log):
        assert load_helm_records() == []

    def test_returns_helm_record_instances(self, helm_log):
        append_helm_record(_rec())
        records = load_helm_records()
        assert len(records) == 1
        assert isinstance(records[0], HelmRecord)

    def test_state_round_trips(self, helm_log):
        append_helm_record(_rec(state="PREPARE"))
        records = load_helm_records()
        assert records[0].state == "PREPARE"

    def test_all_fields_round_trip(self, helm_log):
        r = _rec(state="PUSH", cycle_ts=42.0)
        append_helm_record(r)
        loaded = load_helm_records()[0]
        assert loaded.cycle_ts == pytest.approx(42.0)
        assert loaded.admission_rate == pytest.approx(0.80)
        assert loaded.brittleness == pytest.approx(0.1)

    def test_n_limits_returned_records(self, helm_log):
        for i in range(10):
            append_helm_record(_rec(state="ACT", cycle_ts=float(i)))
        records = load_helm_records(n=3)
        assert len(records) == 3

    def test_n_returns_most_recent(self, helm_log):
        states = ["WAIT", "PREPARE", "ACT", "PUSH", "ACT"]
        for i, s in enumerate(states):
            append_helm_record(_rec(state=s, cycle_ts=float(i)))
        records = load_helm_records(n=3)
        assert [r.state for r in records] == ["ACT", "PUSH", "ACT"]

    def test_n_larger_than_file_returns_all(self, helm_log):
        for _ in range(4):
            append_helm_record(_rec())
        assert len(load_helm_records(n=100)) == 4

    def test_malformed_lines_skipped(self, helm_log):
        helm_log.parent.mkdir(parents=True, exist_ok=True)
        with helm_log.open("w") as f:
            f.write("{bad json\n")
            f.write(json.dumps(
                {"state": "ACT", "rationale": "r", "ts": 1.0, "cycle_ts": 1.0,
                 "admission_rate": 0.8, "anomaly_rate": 0.0, "strong_events": 0,
                 "event_count": 0, "brittleness": 0.0, "strain": 0.0}
            ) + "\n")
        records = load_helm_records()
        assert len(records) == 1
        assert records[0].state == "ACT"

    def test_empty_lines_skipped(self, helm_log):
        helm_log.parent.mkdir(parents=True, exist_ok=True)
        with helm_log.open("w") as f:
            f.write("\n\n")
            f.write(json.dumps(
                {"state": "WAIT", "rationale": "r", "ts": 1.0, "cycle_ts": 1.0,
                 "admission_rate": 0.4, "anomaly_rate": 0.1, "strong_events": 0,
                 "event_count": 0, "brittleness": 0.0, "strain": 0.0}
            ) + "\n")
        records = load_helm_records()
        assert len(records) == 1
