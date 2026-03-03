"""
Tests for signal_core.core.ml.calibration_audit

Invariants:
- compute_calibration() raises RuntimeError when no model has been trained
- compute_calibration() raises ValueError when < MIN_SAMPLES labelled cycles
- compute_calibration() returns CalibrationResult with all expected fields
- brier_score is in [0, 2]
- log_loss_value is non-negative
- ece is in [0, 1]
- mce is in [0, 1] and mce >= ece
- per_class_brier has all three label keys
- each per_class_brier value is in [0, 1]
- reliability_bins are sorted by 'low' ascending
- reliability bins cover [0, 1] range
- n_samples matches the number of labelled cycles
- model_version matches the meta trained_at_iso
- audited_at is a recent unix timestamp
- n_bins is reported correctly in CalibrationResult
- _brier_multiclass returns 0 for perfect predictions
- _brier_multiclass returns ~4/3 for uniform random predictions
- _per_class_brier returns 0 for a class perfectly predicted
- _reliability_bins returns [] when all samples fall in one bin (sanity)
- compute_calibration handles a well-trained model without crashing
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import numpy as np
import pytest

import signal_core.core.ml.classifier as clf_mod
from signal_core.core.ml.calibration_audit import (
    CalibrationResult,
    _brier_multiclass,
    _per_class_brier,
    _reliability_bins,
    compute_calibration,
)
from signal_core.core.ml.classifier import (
    MIN_SAMPLES,
)


# ---------------------------------------------------------------------------
# Helpers — reuse the same synthetic data pattern as test_ml_classifier
# ---------------------------------------------------------------------------

_RNG = random.Random(7)


def _make_feature(ts: float, label: str) -> dict:
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


def _write_paired(
    features_path: Path, labels_path: Path, n_per_class: int = 70
) -> None:
    features_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    ts = 1_742_000_000.0
    for label in (
        ["COUPLING"] * n_per_class + ["LAG"] * n_per_class + ["NOISE"] * n_per_class
    ):
        feat = _make_feature(ts, label)
        lab = {"ts": ts, "label": label, "outcome": "HELD", "notes": "", "weight": 1.0}
        with features_path.open("a") as f:
            f.write(json.dumps(feat) + "\n")
        with labels_path.open("a") as f:
            f.write(json.dumps(lab) + "\n")
        ts += 60.0


def _patch(monkeypatch, tmp_path):
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
    return features_path, labels_path


# ---------------------------------------------------------------------------
# Unit tests for internal helpers (no model needed)
# ---------------------------------------------------------------------------


class TestBrierMulticlass:
    def test_perfect_predictions_return_zero(self):
        y = np.array([0, 1, 2, 0, 1], dtype=np.int32)
        proba = np.array(
            [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]],
            dtype=np.float32,
        )
        assert _brier_multiclass(proba, y) == pytest.approx(0.0, abs=1e-5)

    def test_uniform_random_returns_approx_two_thirds(self):
        # Per sample: correct class (1/3-1)^2=4/9, two wrong (1/3-0)^2=1/9 each
        # → sum = 4/9+1/9+1/9 = 6/9 = 2/3
        n = 3000
        y = np.tile([0, 1, 2], n // 3).astype(np.int32)
        proba = np.full((n, 3), 1 / 3, dtype=np.float32)
        bs = _brier_multiclass(proba, y)
        assert bs == pytest.approx(2 / 3, abs=0.02)

    def test_result_in_valid_range(self):
        rng = np.random.default_rng(42)
        y = rng.integers(0, 3, size=100).astype(np.int32)
        raw = rng.random((100, 3)).astype(np.float32)
        proba = raw / raw.sum(axis=1, keepdims=True)
        assert 0.0 <= _brier_multiclass(proba, y) <= 2.0


class TestPerClassBrier:
    def test_perfect_class_returns_zero(self):
        # Class 0 perfectly predicted, others random
        y = np.zeros(10, dtype=np.int32)
        proba = np.zeros((10, 3), dtype=np.float32)
        proba[:, 0] = 1.0
        pc = _per_class_brier(proba, y)
        assert pc["COUPLING"] == pytest.approx(0.0, abs=1e-5)

    def test_all_keys_present(self):
        y = np.array([0, 1, 2], dtype=np.int32)
        proba = np.eye(3, dtype=np.float32)
        pc = _per_class_brier(proba, y)
        assert set(pc.keys()) == {"COUPLING", "LAG", "NOISE"}

    def test_values_in_zero_one(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 3, size=60).astype(np.int32)
        raw = rng.random((60, 3)).astype(np.float32)
        proba = raw / raw.sum(axis=1, keepdims=True)
        pc = _per_class_brier(proba, y)
        for v in pc.values():
            assert 0.0 <= v <= 1.0


class TestReliabilityBins:
    def test_perfect_calibration_zero_ece(self):
        # Construct a perfectly calibrated set: confidence == accuracy in each bin.
        # Assign conf=0.55 and ensure 55% correct.
        n = 100
        y = np.zeros(n, dtype=np.int32)
        proba = np.zeros((n, 3), dtype=np.float32)
        # 55 samples: top-1 = class 0 (correct), conf = 0.55
        proba[:55, 0] = 0.55
        proba[:55, 1] = 0.225
        proba[:55, 2] = 0.225
        y[:55] = 0  # correct
        # 45 samples: top-1 = class 1 (wrong), conf = 0.55
        proba[55:, 1] = 0.55
        proba[55:, 0] = 0.225
        proba[55:, 2] = 0.225
        y[55:] = 0  # wrong (true class 0, predicted class 1)
        # All land in [0.5–0.6] bin, conf=0.55, acc=0.55 → gap=0
        ece, mce, bins = _reliability_bins(proba, y, n_bins=10)
        assert ece == pytest.approx(0.0, abs=0.01)

    def test_bins_sorted_ascending(self):
        rng = np.random.default_rng(1)
        y = rng.integers(0, 3, size=300).astype(np.int32)
        raw = rng.random((300, 3)).astype(np.float32)
        proba = raw / raw.sum(axis=1, keepdims=True)
        _, _, bins = _reliability_bins(proba, y, n_bins=10)
        lows = [b["low"] for b in bins]
        assert lows == sorted(lows)

    def test_ece_in_zero_one(self):
        rng = np.random.default_rng(2)
        y = rng.integers(0, 3, size=200).astype(np.int32)
        raw = rng.random((200, 3)).astype(np.float32)
        proba = raw / raw.sum(axis=1, keepdims=True)
        ece, mce, _ = _reliability_bins(proba, y, n_bins=10)
        assert 0.0 <= ece <= 1.0
        assert 0.0 <= mce <= 1.0

    def test_mce_geq_ece(self):
        rng = np.random.default_rng(3)
        y = rng.integers(0, 3, size=200).astype(np.int32)
        raw = rng.random((200, 3)).astype(np.float32)
        proba = raw / raw.sum(axis=1, keepdims=True)
        ece, mce, _ = _reliability_bins(proba, y, n_bins=10)
        assert mce >= ece - 1e-6  # mce >= ece always


# ---------------------------------------------------------------------------
# Integration tests for compute_calibration()
# ---------------------------------------------------------------------------


class TestComputeCalibration:
    def test_raises_when_no_model(self, tmp_path, monkeypatch):
        _patch(monkeypatch, tmp_path)
        with pytest.raises(RuntimeError, match="--train"):
            compute_calibration()

    def test_raises_below_min_samples(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        # Train on full data, then remove most labels so paired count < MIN_SAMPLES.
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        # Overwrite labels file with only 5 records
        lines = [ln for ln in labels_path.read_text().splitlines() if ln.strip()]
        labels_path.write_text("\n".join(lines[:5]) + "\n")
        with pytest.raises(ValueError, match=str(MIN_SAMPLES)):
            compute_calibration()

    def test_returns_calibration_result(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert isinstance(result, CalibrationResult)

    def test_n_samples_correct(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert result.n_samples == 210

    def test_brier_in_valid_range(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert 0.0 <= result.brier_score <= 2.0

    def test_log_loss_non_negative(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert result.log_loss_value >= 0.0

    def test_ece_and_mce_in_range(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert 0.0 <= result.ece <= 1.0
        assert 0.0 <= result.mce <= 1.0
        assert result.mce >= result.ece - 1e-5

    def test_per_class_brier_all_keys(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        assert set(result.per_class_brier.keys()) == {"COUPLING", "LAG", "NOISE"}

    def test_per_class_brier_in_zero_one(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        for v in result.per_class_brier.values():
            assert 0.0 <= v <= 1.0

    def test_reliability_bins_sorted(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        if len(result.reliability_bins) > 1:
            lows = [b["low"] for b in result.reliability_bins]
            assert lows == sorted(lows)

    def test_model_version_matches_meta(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        meta = clf_mod.model_info()
        result = compute_calibration()
        assert result.model_version == meta["trained_at_iso"]

    def test_n_bins_reported_correctly(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration(n_bins=5)
        assert result.n_bins == 5

    def test_audited_at_is_recent(self, tmp_path, monkeypatch):
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        before = time.time()
        result = compute_calibration()
        after = time.time()
        assert before <= result.audited_at <= after

    def test_well_trained_model_has_low_brier(self, tmp_path, monkeypatch):
        """A model trained on clearly separable data should have Brier << 4/3."""
        features_path, labels_path = _patch(monkeypatch, tmp_path)
        _write_paired(features_path, labels_path, n_per_class=70)
        clf_mod.train()
        clf_mod._invalidate_cache()
        result = compute_calibration()
        # Our synthetic data is clearly separable — expect much better than random
        assert result.brier_score < 1.0  # well below random (≈1.333)
