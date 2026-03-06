"""
Tests for signal_core.core.ml.outcome_log

Modules covered:
- OutcomeRecord (dataclass, to_dict, from_dict)
- _validate
- _load_labels / _save_labels
- _load_features / _find_feature
- write_label
- get_label
- list_unlabelled
- label_stats
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: seed feature and label files
# ---------------------------------------------------------------------------

_TS1 = 1_741_000_000.0
_TS2 = 1_741_100_000.0


def _write_features(ml_dir: Path, records: list[dict]) -> None:
    ml_dir.mkdir(parents=True, exist_ok=True)
    features = ml_dir / "features.jsonl"
    with features.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _write_labels(ml_dir: Path, records: list[dict]) -> None:
    ml_dir.mkdir(parents=True, exist_ok=True)
    labels = ml_dir / "labels.jsonl"
    with labels.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ===========================================================================
# OutcomeRecord
# ===========================================================================


class TestOutcomeRecord:
    def _make(self, **kw):
        from signal_core.core.ml.outcome_log import OutcomeRecord

        defaults = dict(
            ts=_TS1,
            label="NOISE",
            outcome="HELD",
            notes="",
            labelled_at=0.0,
            weight=1.0,
        )
        defaults.update(kw)
        return OutcomeRecord(**defaults)

    def test_to_dict_contains_all_fields(self):
        rec = self._make()
        d = rec.to_dict()
        assert d["ts"] == _TS1
        assert d["label"] == "NOISE"
        assert d["outcome"] == "HELD"

    def test_from_dict_round_trip(self):
        from signal_core.core.ml.outcome_log import OutcomeRecord

        rec = self._make(label="COUPLING", outcome="ACTED", notes="ok", weight=2.0)
        d = rec.to_dict()
        rec2 = OutcomeRecord.from_dict(d)
        assert rec2.label == "COUPLING"
        assert rec2.weight == 2.0
        assert rec2.notes == "ok"

    def test_from_dict_defaults(self):
        from signal_core.core.ml.outcome_log import OutcomeRecord

        rec = OutcomeRecord.from_dict(
            {"ts": "1000.0", "label": "LAG", "outcome": "MONITORED"}
        )
        assert rec.notes == ""
        assert rec.weight == 1.0
        assert rec.labelled_at == 0.0


# ===========================================================================
# _validate
# ===========================================================================


class TestValidate:
    def _call(self, label, outcome):
        from signal_core.core.ml.outcome_log import _validate

        _validate(label, outcome)

    def test_valid_noise_held(self):
        self._call("NOISE", "HELD")

    def test_valid_coupling_acted(self):
        self._call("COUPLING", "ACTED")

    def test_valid_lag_monitored(self):
        self._call("LAG", "MONITORED")

    def test_invalid_label_raises(self):
        from signal_core.core.ml.outcome_log import _validate

        with pytest.raises(ValueError, match="Invalid label"):
            _validate("WRONG", "HELD")

    def test_invalid_outcome_raises(self):
        from signal_core.core.ml.outcome_log import _validate

        with pytest.raises(ValueError, match="Invalid outcome"):
            _validate("NOISE", "WRONG")


# ===========================================================================
# _load_labels / _save_labels
# ===========================================================================


class TestLoadSaveLabels:
    def test_empty_when_no_file(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with patch.object(mod, "_LABELS_PATH", tmp_path / "labels.jsonl"):
            result = mod._load_labels()
        assert result == {}

    def test_round_trip(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod
        from signal_core.core.ml.outcome_log import OutcomeRecord

        lp = tmp_path / "labels.jsonl"
        rec = OutcomeRecord(
            ts=_TS1,
            label="NOISE",
            outcome="HELD",
            notes="x",
            labelled_at=0.0,
            weight=1.0,
        )

        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod._save_labels({_TS1: rec})
            loaded = mod._load_labels()

        assert _TS1 in loaded
        assert loaded[_TS1].label == "NOISE"

    def test_corrupt_lines_skipped(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        lp = tmp_path / "labels.jsonl"
        lp.write_text(
            'corrupt\n{"ts":1000.0,"label":"NOISE","outcome":"HELD","notes":"","labelled_at":0.0,"weight":1.0}\n'
        )

        with patch.object(mod, "_LABELS_PATH", lp):
            result = mod._load_labels()
        assert 1000.0 in result

    def test_save_sorts_by_ts(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod
        from signal_core.core.ml.outcome_log import OutcomeRecord

        lp = tmp_path / "labels.jsonl"
        r1 = OutcomeRecord(
            ts=_TS2,
            label="NOISE",
            outcome="HELD",
            notes="",
            labelled_at=0.0,
            weight=1.0,
        )
        r2 = OutcomeRecord(
            ts=_TS1, label="LAG", outcome="ACTED", notes="", labelled_at=0.0, weight=1.0
        )

        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod._save_labels({_TS2: r1, _TS1: r2})
            lines = [json.loads(ln) for ln in lp.read_text().splitlines() if ln.strip()]

        assert lines[0]["ts"] == _TS1
        assert lines[1]["ts"] == _TS2


# ===========================================================================
# _load_features
# ===========================================================================


class TestLoadFeatures:
    def test_empty_when_no_file(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with patch.object(mod, "_FEATURES_PATH", tmp_path / "features.jsonl"):
            result = mod._load_features()
        assert result == []

    def test_loads_records(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1, "val": 1}) + "\n")

        with patch.object(mod, "_FEATURES_PATH", fp):
            result = mod._load_features()
        assert len(result) == 1
        assert result[0]["ts"] == _TS1

    def test_corrupt_lines_skipped(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        fp = tmp_path / "features.jsonl"
        fp.write_text("corrupt\n" + json.dumps({"ts": _TS1}) + "\n")

        with patch.object(mod, "_FEATURES_PATH", fp):
            result = mod._load_features()
        assert len(result) == 1


# ===========================================================================
# write_label
# ===========================================================================


class TestWriteLabel:
    def _setup(self, tmp_path):
        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1, "val": 1}) + "\n")
        return tmp_path / "labels.jsonl", fp

    def test_write_and_retrieve(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        lp, fp = self._setup(tmp_path)
        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            rec = mod.write_label(_TS1, "COUPLING", "ACTED", notes="test", weight=2.0)

        assert rec.label == "COUPLING"
        assert rec.weight == 2.0

    def test_invalid_label_raises(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        lp, fp = self._setup(tmp_path)
        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            with pytest.raises(ValueError, match="Invalid label"):
                mod.write_label(_TS1, "INVALID", "HELD")

    def test_unknown_ts_raises(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        lp, fp = self._setup(tmp_path)
        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            with pytest.raises(ValueError, match="No feature record"):
                mod.write_label(9999.0, "NOISE", "HELD")

    def test_overwrite_existing(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        lp, fp = self._setup(tmp_path)
        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod.write_label(_TS1, "NOISE", "HELD")
            mod.write_label(_TS1, "LAG", "ACTED")
            loaded = mod._load_labels()
        assert loaded[_TS1].label == "LAG"


# ===========================================================================
# get_label
# ===========================================================================


class TestGetLabel:
    def test_returns_none_when_not_labelled(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with patch.object(mod, "_LABELS_PATH", tmp_path / "missing.jsonl"):
            result = mod.get_label(_TS1)
        assert result is None

    def test_returns_record_when_labelled(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod
        from signal_core.core.ml.outcome_log import OutcomeRecord

        lp = tmp_path / "labels.jsonl"
        rec = OutcomeRecord(
            ts=_TS1,
            label="LAG",
            outcome="MONITORED",
            notes="",
            labelled_at=0.0,
            weight=1.0,
        )
        with (
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod._save_labels({_TS1: rec})
            result = mod.get_label(_TS1)
        assert result is not None
        assert result.label == "LAG"


# ===========================================================================
# list_unlabelled
# ===========================================================================


class TestListUnlabelled:
    def test_all_unlabelled_when_no_labels(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1}) + "\n" + json.dumps({"ts": _TS2}) + "\n")
        with (
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "_LABELS_PATH", tmp_path / "empty.jsonl"),
        ):
            result = mod.list_unlabelled()
        assert len(result) == 2

    def test_labelled_excluded(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod
        from signal_core.core.ml.outcome_log import OutcomeRecord

        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1}) + "\n" + json.dumps({"ts": _TS2}) + "\n")
        lp = tmp_path / "labels.jsonl"
        rec = OutcomeRecord(
            ts=_TS1,
            label="NOISE",
            outcome="HELD",
            notes="",
            labelled_at=0.0,
            weight=1.0,
        )
        with (
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod._save_labels({_TS1: rec})
            result = mod.list_unlabelled()
        assert len(result) == 1
        assert float(result[0]["ts"]) == _TS2

    def test_most_recent_first(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1}) + "\n" + json.dumps({"ts": _TS2}) + "\n")
        with (
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "_LABELS_PATH", tmp_path / "empty.jsonl"),
        ):
            result = mod.list_unlabelled()
        assert float(result[0]["ts"]) > float(result[1]["ts"])

    def test_limit_respected(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        fp = tmp_path / "features.jsonl"
        with fp.open("w") as f:
            for i in range(10):
                f.write(json.dumps({"ts": float(i)}) + "\n")
        with (
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "_LABELS_PATH", tmp_path / "empty.jsonl"),
        ):
            result = mod.list_unlabelled(limit=3)
        assert len(result) == 3


# ===========================================================================
# label_stats
# ===========================================================================


class TestLabelStats:
    def test_no_features_no_labels(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with (
            patch.object(mod, "_FEATURES_PATH", tmp_path / "f.jsonl"),
            patch.object(mod, "_LABELS_PATH", tmp_path / "l.jsonl"),
        ):
            s = mod.label_stats()
        assert s["total_features"] == 0
        assert s["total_labelled"] == 0
        assert s["coverage_pct"] == 0.0
        assert s["ready_to_train"] is False

    def test_coverage_calculated(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod
        from signal_core.core.ml.outcome_log import OutcomeRecord

        fp = tmp_path / "features.jsonl"
        fp.write_text(json.dumps({"ts": _TS1}) + "\n" + json.dumps({"ts": _TS2}) + "\n")
        lp = tmp_path / "labels.jsonl"
        rec = OutcomeRecord(
            ts=_TS1,
            label="NOISE",
            outcome="HELD",
            notes="",
            labelled_at=0.0,
            weight=1.0,
        )

        with (
            patch.object(mod, "_FEATURES_PATH", fp),
            patch.object(mod, "_LABELS_PATH", lp),
            patch.object(mod, "ML_DIR", tmp_path),
        ):
            mod._save_labels({_TS1: rec})
            s = mod.label_stats()

        assert s["total_features"] == 2
        assert s["total_labelled"] == 1
        assert s["coverage_pct"] == 50.0

    def test_ready_to_train_false_below_200(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with (
            patch.object(mod, "_FEATURES_PATH", tmp_path / "f.jsonl"),
            patch.object(mod, "_LABELS_PATH", tmp_path / "l.jsonl"),
        ):
            s = mod.label_stats()
        assert s["ready_to_train"] is False

    def test_label_counts_included(self, tmp_path):
        import signal_core.core.ml.outcome_log as mod

        with (
            patch.object(mod, "_FEATURES_PATH", tmp_path / "f.jsonl"),
            patch.object(mod, "_LABELS_PATH", tmp_path / "l.jsonl"),
        ):
            s = mod.label_stats()
        assert "NOISE" in s["label_counts"]
        assert "COUPLING" in s["label_counts"]
        assert "LAG" in s["label_counts"]
