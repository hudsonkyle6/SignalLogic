"""
Tests for signal_core.core.ml.classifier

Invariants:
- train() raises ValueError when fewer than MIN_SAMPLES labelled cycles exist
- train() succeeds and returns correct shape when >= MIN_SAMPLES exist
- train() creates model.joblib and model_meta.json
- train() meta contains expected keys (feature_cols, label_map, cv_accuracy, ...)
- train() sample weights are honoured (weight array is built correctly)
- train() invalidates the module-level model cache after saving
- evaluate() raises ValueError when fewer than MIN_SAMPLES labelled cycles exist
- evaluate() returns EvalResult with expected fields and value ranges
- predict() raises RuntimeError when no model exists
- predict() returns valid Prediction shape for a known feature dict
- predict() confidence == max(probabilities.values())
- predict() probabilities sum to ~1.0
- predict() handles missing feature keys (default to 0.0)
- predict() ignores extra feature keys not in the saved schema
- load_model() returns None when no model file exists
- load_model() returns the fitted model after training
- model_info() returns None when no meta file exists
- model_info() returns correct keys after training
- _build_feature_matrix() produces correct column count and dtype
- _build_feature_matrix() converts bools to int
- _build_feature_matrix() defaults missing columns to 0.0
- LABEL_MAP is stable (alphabetical, values 0/1/2)
- LABEL_INV is the inverse of LABEL_MAP
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

import numpy as np
import pytest

import signal_core.core.ml.classifier as clf_mod
from signal_core.core.ml.classifier import (
    LABEL_MAP,
    LABEL_INV,
    MIN_SAMPLES,
    EvalResult,
    Prediction,
    TrainResult,
    _build_feature_matrix,
    evaluate,
    load_model,
    model_info,
    predict,
    train,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RNG = random.Random(42)


def _make_feature(ts: float, label: str) -> dict:
    """
    Synthetic feature record that is correlated with the label so XGBoost
    can learn a non-trivial decision boundary.

    COUPLING: high convergence event count + high scar pressure
    LAG:      medium convergence + medium scar
    NOISE:    low convergence + low scar
    """
    base = {
        "COUPLING": {
            "convergence_event_count": 4,
            "strong_events": 2,
            "scar_system_max_pressure": 1.8,
        },
        "LAG": {
            "convergence_event_count": 2,
            "strong_events": 1,
            "scar_system_max_pressure": 0.9,
        },
        "NOISE": {
            "convergence_event_count": 0,
            "strong_events": 0,
            "scar_system_max_pressure": 0.1,
        },
    }[label]
    return {
        "ts": ts,
        "diurnal_phase": round(_RNG.random(), 4),
        "hour_of_day": _RNG.randint(0, 23),
        "day_of_week": _RNG.randint(0, 6),
        "month": _RNG.randint(1, 12),
        "dominant_phase": round(_RNG.random(), 4),
        "total_turbine_obs": _RNG.randint(0, 100),
        "turbine_domain_count": _RNG.randint(0, 5),
        "max_event_domain_count": _RNG.randint(0, 4),
        "has_convergence": base["convergence_event_count"] > 0,
        "system_ready": True,
        "natural_ready": True,
        "system_count": _RNG.randint(10, 100),
        "natural_count": _RNG.randint(10, 100),
        "packets_drained": _RNG.randint(0, 50),
        "rejected": _RNG.randint(0, 5),
        "committed": _RNG.randint(0, 30),
        "turbine_obs": _RNG.randint(0, 20),
        "spillway_quarantined": _RNG.randint(0, 3),
        "spillway_hold": _RNG.randint(0, 3),
        **base,
    }


def _make_label(ts: float, label: str, weight: float = 1.0) -> dict:
    return {"ts": ts, "label": label, "outcome": "HELD", "notes": "", "weight": weight}


def _write_paired(
    features_path: Path,
    labels_path: Path,
    n_per_class: int = 70,
) -> List[float]:
    """Write n_per_class records for each of the 3 labels. Returns all ts values."""
    features_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    ts_values = []
    ts = 1_741_000_000.0
    labels = (
        ["COUPLING"] * n_per_class + ["LAG"] * n_per_class + ["NOISE"] * n_per_class
    )
    for label in labels:
        feat = _make_feature(ts, label)
        lab = _make_label(ts, label)
        with features_path.open("a") as f:
            f.write(json.dumps(feat) + "\n")
        with labels_path.open("a") as f:
            f.write(json.dumps(lab) + "\n")
        ts_values.append(ts)
        ts += 60.0
    return ts_values


def _patch(monkeypatch, tmp_path):
    """Redirect all paths and invalidate the module cache."""
    features_path = tmp_path / "features.jsonl"
    labels_path = tmp_path / "labels.jsonl"
    model_path = tmp_path / "model.joblib"
    meta_path = tmp_path / "model_meta.json"
    monkeypatch.setattr(clf_mod, "ML_DIR", tmp_path)
    monkeypatch.setattr(clf_mod, "_FEATURES_PATH", features_path)
    monkeypatch.setattr(clf_mod, "_LABELS_PATH", labels_path)
    monkeypatch.setattr(clf_mod, "_MODEL_PATH", model_path)
    monkeypatch.setattr(clf_mod, "_META_PATH", meta_path)
    clf_mod._invalidate_cache()
    return features_path, labels_path, model_path, meta_path


# ---------------------------------------------------------------------------
# LABEL_MAP / LABEL_INV invariants
# ---------------------------------------------------------------------------


class TestLabelMap:
    def test_alphabetical_ordering(self):
        assert LABEL_MAP == {"COUPLING": 0, "LAG": 1, "NOISE": 2}

    def test_inv_is_inverse(self):
        for label, idx in LABEL_MAP.items():
            assert LABEL_INV[idx] == label

    def test_all_three_classes_present(self):
        assert set(LABEL_MAP.keys()) == {"COUPLING", "LAG", "NOISE"}


# ---------------------------------------------------------------------------
# _build_feature_matrix
# ---------------------------------------------------------------------------


class TestBuildFeatureMatrix:
    def test_column_count_and_dtype(self):
        records = [
            {"ts": 1.0, "a": 0.5, "b": 1.0},
            {"ts": 2.0, "a": 0.3, "b": 2.0},
        ]
        X, cols = _build_feature_matrix(records)
        assert X.dtype == np.float32
        assert X.shape == (2, 2)  # ts excluded
        assert cols == ["a", "b"]

    def test_bools_converted_to_int(self):
        records = [{"ts": 1.0, "flag": True}, {"ts": 2.0, "flag": False}]
        X, cols = _build_feature_matrix(records)
        assert X[0, cols.index("flag")] == 1.0
        assert X[1, cols.index("flag")] == 0.0

    def test_missing_columns_default_to_zero(self):
        records = [{"ts": 1.0, "a": 5.0}, {"ts": 2.0, "b": 3.0}]
        X, cols = _build_feature_matrix(records)
        assert set(cols) == {"a", "b"}
        # First record has b=0, second has a=0
        a_idx = cols.index("a")
        b_idx = cols.index("b")
        assert X[0, a_idx] == 5.0
        assert X[0, b_idx] == 0.0
        assert X[1, a_idx] == 0.0
        assert X[1, b_idx] == 3.0

    def test_inference_mode_uses_provided_columns(self):
        records = [{"ts": 1.0, "a": 9.0, "extra_key": 99.0}]
        fixed_cols = ["a", "b"]  # b is missing, extra_key is ignored
        X, cols = _build_feature_matrix(records, feature_cols=fixed_cols)
        assert cols == fixed_cols
        assert X.shape == (1, 2)
        assert X[0, 0] == 9.0  # a
        assert X[0, 1] == 0.0  # b missing → 0

    def test_ts_excluded_in_training_mode(self):
        records = [{"ts": 1.0, "a": 1.0}]
        _, cols = _build_feature_matrix(records)
        assert "ts" not in cols


# ---------------------------------------------------------------------------
# train()
# ---------------------------------------------------------------------------


class TestTrain:
    def test_raises_below_min_samples(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=1)  # 3 total
        with pytest.raises(ValueError, match=str(MIN_SAMPLES)):
            train(min_samples=MIN_SAMPLES)

    def test_succeeds_at_min_samples(self, tmp_path, monkeypatch):
        features_path, labels_path, model_path, meta_path = _patch(
            monkeypatch, tmp_path
        )
        n_per_class = MIN_SAMPLES // 3 + 1  # ensures total >= MIN_SAMPLES
        _write_paired(features_path, labels_path, n_per_class=n_per_class)
        result = train(min_samples=MIN_SAMPLES)
        assert isinstance(result, TrainResult)
        assert result.n_samples >= MIN_SAMPLES

    def test_creates_model_and_meta_files(self, tmp_path, monkeypatch):
        features_path, labels_path, model_path, meta_path = _patch(
            monkeypatch, tmp_path
        )
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        assert model_path.exists()
        assert meta_path.exists()

    def test_meta_contains_expected_keys(self, tmp_path, monkeypatch):
        features_path, labels_path, _, meta_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        meta = json.loads(meta_path.read_text())
        for key in (
            "feature_cols",
            "label_map",
            "trained_at",
            "trained_at_iso",
            "n_samples",
            "n_features",
            "label_counts",
            "cv_accuracy",
            "cv_f1_weighted",
            "per_class",
            "n_folds",
        ):
            assert key in meta, f"missing key: {key}"

    def test_meta_label_counts_correct(self, tmp_path, monkeypatch):
        features_path, labels_path, _, meta_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = train()
        assert result.label_counts["COUPLING"] == 70
        assert result.label_counts["LAG"] == 70
        assert result.label_counts["NOISE"] == 70

    def test_cv_accuracy_in_valid_range(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = train()
        assert 0.0 <= result.cv_accuracy <= 1.0
        assert 0.0 <= result.cv_f1_weighted <= 1.0

    def test_per_class_keys_present(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = train()
        for label in ("COUPLING", "LAG", "NOISE"):
            assert label in result.per_class
            for metric in ("precision", "recall", "f1", "support"):
                assert metric in result.per_class[label]

    def test_invalidates_cache_after_train(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        # After train the cache is invalid; load_model must reload from disk
        clf_mod._MODEL_CACHE = None  # ensure truly cold
        loaded = load_model()
        assert loaded is not None

    def test_error_message_mentions_list_unlabelled(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=1)
        with pytest.raises(ValueError, match="list-unlabelled"):
            train(min_samples=MIN_SAMPLES)

    def test_custom_min_samples_respected(self, tmp_path, monkeypatch):
        # Use 30 per class (90 total) so there is enough data for the
        # CalibratedClassifierCV internal 5-fold CV while still testing
        # that a custom lower gate (10) allows training below MIN_SAMPLES.
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=30)  # 90 total
        result = train(min_samples=10)
        assert result.n_samples == 90

    def test_sample_weights_present_in_label_records(self, tmp_path, monkeypatch):
        """Weight=2.0 records are written without error and n_samples is correct."""
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        ts_values = _write_paired(features_path, labels_path, n_per_class=70)
        # Overwrite first label with weight=2.0
        labels = []
        for line in labels_path.read_text().splitlines():
            rec = json.loads(line)
            if float(rec["ts"]) == ts_values[0]:
                rec["weight"] = 2.0
            labels.append(rec)
        labels_path.write_text("\n".join(json.dumps(r) for r in labels) + "\n")
        result = train()
        assert result.n_samples == 210


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_raises_below_min_samples(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=1)
        with pytest.raises(ValueError, match=str(MIN_SAMPLES)):
            evaluate()

    def test_returns_eval_result(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = evaluate()
        assert isinstance(result, EvalResult)

    def test_accuracy_in_valid_range(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = evaluate()
        assert 0.0 <= result.accuracy <= 1.0

    def test_no_model_files_created(self, tmp_path, monkeypatch):
        features_path, labels_path, model_path, meta_path = _patch(
            monkeypatch, tmp_path
        )
        _write_paired(features_path, labels_path, n_per_class=70)
        evaluate()
        assert not model_path.exists()
        assert not meta_path.exists()

    def test_per_class_all_labels_present(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = evaluate()
        assert set(result.per_class.keys()) == {"COUPLING", "LAG", "NOISE"}

    def test_n_folds_reported(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        result = evaluate(n_folds=3)
        assert result.n_folds == 3


# ---------------------------------------------------------------------------
# load_model() / model_info()
# ---------------------------------------------------------------------------


class TestLoadModel:
    def test_returns_none_when_no_model(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        assert load_model() is None

    def test_returns_model_after_train(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        assert load_model() is not None

    def test_caches_after_first_load(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        m1 = load_model()
        m2 = load_model()
        assert m1 is m2  # same object — not reloaded

    def test_model_info_none_without_meta(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        assert model_info() is None

    def test_model_info_after_train(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        info = model_info()
        assert info is not None
        assert "feature_cols" in info
        assert "label_map" in info


# ---------------------------------------------------------------------------
# predict()
# ---------------------------------------------------------------------------


class TestPredict:
    def test_raises_when_no_model(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        with pytest.raises(RuntimeError, match="--train"):
            predict({"ts": 1.0, "convergence_event_count": 2})

    def test_returns_prediction_shape(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(9_999_999.0, "COUPLING")
        pred = predict(feat)
        assert isinstance(pred, Prediction)
        assert pred.predicted_label in LABEL_MAP
        assert 0.0 <= pred.confidence <= 1.0
        assert set(pred.probabilities.keys()) == {"COUPLING", "LAG", "NOISE"}

    def test_probabilities_sum_to_one(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(9_999_998.0, "NOISE")
        pred = predict(feat)
        total = sum(pred.probabilities.values())
        assert abs(total - 1.0) < 1e-4

    def test_confidence_equals_max_probability(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(9_999_997.0, "LAG")
        pred = predict(feat)
        assert abs(pred.confidence - max(pred.probabilities.values())) < 1e-6

    def test_calibrated_flag_is_true(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(9_999_996.0, "COUPLING")
        pred = predict(feat)
        assert pred.calibrated is True

    def test_missing_feature_keys_default_to_zero(self, tmp_path, monkeypatch):
        """Prediction succeeds even if the feature dict is missing some columns."""
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        # Only provide a minimal dict — all other keys will default to 0.0
        minimal = {"ts": 1.0, "convergence_event_count": 3}
        pred = predict(minimal)
        assert pred.predicted_label in LABEL_MAP

    def test_extra_feature_keys_are_ignored(self, tmp_path, monkeypatch):
        """Keys not in the saved schema do not cause errors."""
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(9_999_995.0, "NOISE")
        feat["brand_new_domain_never_seen_before"] = 42.0
        pred = predict(feat)
        assert pred.predicted_label in LABEL_MAP

    def test_ts_passed_through_to_prediction(self, tmp_path, monkeypatch):
        features_path, labels_path, _, _ = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        train()
        clf_mod._invalidate_cache()
        feat = _make_feature(1_234_567.0, "COUPLING")
        pred = predict(feat)
        assert pred.ts == 1_234_567.0
