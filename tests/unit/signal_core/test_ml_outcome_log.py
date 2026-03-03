"""
Tests for signal_core.core.ml.outcome_log

Invariants:
- write_label rejects invalid label values
- write_label rejects invalid outcome values
- write_label raises ValueError when ts has no matching feature record
- write_label creates labels.jsonl on first write
- write_label stores all fields correctly
- write_label overwrites existing label for same ts (idempotent / last-write-wins)
- write_label preserves other labels when overwriting one
- get_label returns the OutcomeRecord for a known ts
- get_label returns None for an unknown ts
- list_unlabelled returns feature records with no matching label
- list_unlabelled excludes already-labelled ts values
- list_unlabelled returns most-recent first
- list_unlabelled respects the limit parameter
- list_unlabelled returns empty list when all cycles are labelled
- label_stats returns correct counts and coverage
- label_stats reports ready_to_train=True only at >= 200 labels
- label_stats handles empty files gracefully
- OutcomeRecord round-trips through to_dict / from_dict
- OutcomeRecord.from_dict fills defaults for optional fields
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import signal_core.core.ml.outcome_log as ol_mod
from signal_core.core.ml.outcome_log import (
    OutcomeRecord,
    get_label,
    label_stats,
    list_unlabelled,
    write_label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_feature(path: Path, ts: float, **extra) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": ts, "convergence_event_count": 1, "strong_events": 0, **extra}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _patch(monkeypatch, tmp_path):
    """Redirect ML_DIR, _FEATURES_PATH, and _LABELS_PATH to tmp_path."""
    features_path = tmp_path / "features.jsonl"
    labels_path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(ol_mod, "ML_DIR", tmp_path)
    monkeypatch.setattr(ol_mod, "_FEATURES_PATH", features_path)
    monkeypatch.setattr(ol_mod, "_LABELS_PATH", labels_path)
    return features_path, labels_path


# ---------------------------------------------------------------------------
# OutcomeRecord
# ---------------------------------------------------------------------------


class TestOutcomeRecord:
    def test_round_trip(self):
        rec = OutcomeRecord(
            ts=1_000.0,
            label="COUPLING",
            outcome="ACTED",
            notes="test note",
            labelled_at=2_000.0,
            weight=1.5,
        )
        assert OutcomeRecord.from_dict(rec.to_dict()) == rec

    def test_from_dict_defaults_optional_fields(self):
        minimal = {"ts": 1.0, "label": "NOISE", "outcome": "HELD"}
        rec = OutcomeRecord.from_dict(minimal)
        assert rec.notes == ""
        assert rec.labelled_at == 0.0
        assert rec.weight == 1.0

    def test_to_dict_is_json_serialisable(self):
        rec = OutcomeRecord(
            ts=1.0,
            label="LAG",
            outcome="MONITORED",
            notes="",
            labelled_at=2.0,
            weight=1.0,
        )
        raw = json.dumps(rec.to_dict())
        assert json.loads(raw)["label"] == "LAG"


# ---------------------------------------------------------------------------
# write_label — validation
# ---------------------------------------------------------------------------


class TestWriteLabelValidation:
    def test_invalid_label_raises(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        with pytest.raises(ValueError, match="Invalid label"):
            write_label(ts=100.0, label="WRONG", outcome="ACTED")

    def test_invalid_outcome_raises(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        with pytest.raises(ValueError, match="Invalid outcome"):
            write_label(ts=100.0, label="NOISE", outcome="IGNORED")

    def test_unknown_ts_raises(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="No feature record found"):
            write_label(ts=999.0, label="NOISE", outcome="HELD")

    def test_unknown_ts_error_mentions_list_unlabelled(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="list-unlabelled"):
            write_label(ts=999.0, label="NOISE", outcome="HELD")


# ---------------------------------------------------------------------------
# write_label — persistence
# ---------------------------------------------------------------------------


class TestWriteLabelPersistence:
    def test_creates_labels_file(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        assert labels_path.exists()

    def test_stores_all_fields(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        before = time.time()
        write_label(
            ts=100.0, label="COUPLING", outcome="ACTED", notes="good signal", weight=2.0
        )
        after = time.time()
        line = labels_path.read_text().strip()
        rec = OutcomeRecord.from_dict(json.loads(line))
        assert rec.ts == 100.0
        assert rec.label == "COUPLING"
        assert rec.outcome == "ACTED"
        assert rec.notes == "good signal"
        assert rec.weight == 2.0
        assert before <= rec.labelled_at <= after

    def test_overwrite_existing_label(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        write_label(ts=100.0, label="COUPLING", outcome="ACTED")
        lines = [ln for ln in labels_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1
        assert json.loads(lines[0])["label"] == "COUPLING"

    def test_overwrite_preserves_other_labels(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        _write_feature(features_path, ts=200.0)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        write_label(ts=200.0, label="LAG", outcome="MONITORED")
        write_label(ts=100.0, label="COUPLING", outcome="ACTED")  # overwrite first
        lines = [ln for ln in labels_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 2
        records = {json.loads(ln)["ts"]: json.loads(ln) for ln in lines}
        assert records[100.0]["label"] == "COUPLING"
        assert records[200.0]["label"] == "LAG"

    def test_all_valid_label_values_accepted(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for i, label in enumerate(["NOISE", "COUPLING", "LAG"]):
            ts = float(100 + i)
            _write_feature(features_path, ts=ts)
            rec = write_label(ts=ts, label=label, outcome="HELD")
            assert rec.label == label

    def test_all_valid_outcome_values_accepted(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for i, outcome in enumerate(["ACTED", "HELD", "MONITORED"]):
            ts = float(200 + i)
            _write_feature(features_path, ts=ts)
            rec = write_label(ts=ts, label="NOISE", outcome=outcome)
            assert rec.outcome == outcome


# ---------------------------------------------------------------------------
# get_label
# ---------------------------------------------------------------------------


class TestGetLabel:
    def test_returns_record_for_known_ts(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        write_label(ts=100.0, label="LAG", outcome="MONITORED")
        rec = get_label(100.0)
        assert rec is not None
        assert rec.label == "LAG"

    def test_returns_none_for_unknown_ts(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        assert get_label(999.0) is None

    def test_returns_none_when_labels_file_missing(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        assert get_label(1.0) is None


# ---------------------------------------------------------------------------
# list_unlabelled
# ---------------------------------------------------------------------------


class TestListUnlabelled:
    def test_returns_unlabelled_features(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        _write_feature(features_path, ts=200.0)
        unlabelled = list_unlabelled()
        ts_values = {float(f["ts"]) for f in unlabelled}
        assert 100.0 in ts_values
        assert 200.0 in ts_values

    def test_excludes_labelled_ts(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        _write_feature(features_path, ts=200.0)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        unlabelled = list_unlabelled()
        ts_values = {float(f["ts"]) for f in unlabelled}
        assert 100.0 not in ts_values
        assert 200.0 in ts_values

    def test_most_recent_first(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for ts in [100.0, 300.0, 200.0]:
            _write_feature(features_path, ts=ts)
        unlabelled = list_unlabelled()
        timestamps = [float(f["ts"]) for f in unlabelled]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_respects_limit(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for ts in range(10):
            _write_feature(features_path, ts=float(ts))
        assert len(list_unlabelled(limit=3)) == 3

    def test_empty_when_all_labelled(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        _write_feature(features_path, ts=100.0)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        assert list_unlabelled() == []

    def test_empty_when_no_features(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        assert list_unlabelled() == []


# ---------------------------------------------------------------------------
# label_stats
# ---------------------------------------------------------------------------


class TestLabelStats:
    def test_empty_returns_zeros(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        s = label_stats()
        assert s["total_features"] == 0
        assert s["total_labelled"] == 0
        assert s["coverage_pct"] == 0.0
        assert s["ready_to_train"] is False

    def test_counts_features_and_labels(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for ts in [100.0, 200.0, 300.0]:
            _write_feature(features_path, ts=ts)
        write_label(ts=100.0, label="NOISE", outcome="HELD")
        s = label_stats()
        assert s["total_features"] == 3
        assert s["total_labelled"] == 1
        assert s["coverage_pct"] == pytest.approx(33.3, abs=0.1)

    def test_label_counts_correct(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        combos = [
            (100.0, "NOISE", "HELD"),
            (200.0, "COUPLING", "ACTED"),
            (300.0, "COUPLING", "MONITORED"),
            (400.0, "LAG", "ACTED"),
        ]
        for ts, label, outcome in combos:
            _write_feature(features_path, ts=ts)
            write_label(ts=ts, label=label, outcome=outcome)
        s = label_stats()
        assert s["label_counts"]["NOISE"] == 1
        assert s["label_counts"]["COUPLING"] == 2
        assert s["label_counts"]["LAG"] == 1

    def test_outcome_counts_correct(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for i, outcome in enumerate(["ACTED", "ACTED", "HELD", "MONITORED"]):
            ts = float(100 + i)
            _write_feature(features_path, ts=ts)
            write_label(ts=ts, label="NOISE", outcome=outcome)
        s = label_stats()
        assert s["outcome_counts"]["ACTED"] == 2
        assert s["outcome_counts"]["HELD"] == 1
        assert s["outcome_counts"]["MONITORED"] == 1

    def test_ready_to_train_false_below_200(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for ts in range(199):
            _write_feature(features_path, ts=float(ts))
            write_label(ts=float(ts), label="NOISE", outcome="HELD")
        assert label_stats()["ready_to_train"] is False

    def test_ready_to_train_true_at_200(self, tmp_path, monkeypatch):
        features_path, _ = _patch(monkeypatch, tmp_path)
        for ts in range(200):
            _write_feature(features_path, ts=float(ts))
            write_label(ts=float(ts), label="NOISE", outcome="HELD")
        assert label_stats()["ready_to_train"] is True
