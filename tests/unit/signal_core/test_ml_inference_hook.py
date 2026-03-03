"""
Tests for the ML inference hook wired into hydro_run.py

Invariants:
- CycleResult has ml_prediction field defaulting to None
- _run_ml_inference returns result unchanged when features dict is empty
- _run_ml_inference returns result unchanged when load_model() returns None
- _run_ml_inference populates ml_prediction when model is available
- ml_prediction dict has all expected keys
- ml_prediction confidence is in [0, 1]
- ml_prediction predicted_label is a valid label
- _run_ml_inference returns result unchanged on predict() exception
- _run_ml_inference returns result unchanged on load_model() exception
- CycleResult.ml_prediction serialises cleanly with dataclasses.asdict
"""

from __future__ import annotations

import dataclasses


from signal_core.core.hydro_run import _run_ml_inference
from signal_core.core.hydro_run_cadence import CycleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(**kwargs) -> CycleResult:
    defaults = dict(
        cycle_ts=1_000.0,
        packets_drained=5,
        rejected=1,
        committed=3,
        turbine_obs=2,
        spillway_quarantined=0,
        spillway_hold=0,
    )
    defaults.update(kwargs)
    return CycleResult(**defaults)


def _make_fake_prediction(label: str = "NOISE"):
    """Return a minimal fake Prediction-like object."""

    class _FakePred:
        predicted_label = label
        confidence = 0.85
        probabilities = {"COUPLING": 0.05, "LAG": 0.10, "NOISE": 0.85}
        model_version = "2026-03-03T00:00:00+00:00"
        calibrated = True

    return _FakePred()


# ---------------------------------------------------------------------------
# CycleResult shape
# ---------------------------------------------------------------------------


class TestCycleResultShape:
    def test_ml_prediction_defaults_to_none(self):
        result = _make_result()
        assert result.ml_prediction is None

    def test_ml_prediction_accepts_dict(self):
        result = _make_result(
            ml_prediction={
                "predicted_label": "NOISE",
                "confidence": 0.9,
                "probabilities": {"COUPLING": 0.05, "LAG": 0.05, "NOISE": 0.9},
                "model_version": "2026-03-03T00:00:00+00:00",
                "calibrated": True,
            }
        )
        assert result.ml_prediction["predicted_label"] == "NOISE"

    def test_dataclasses_asdict_serialises_ml_prediction(self):
        import json

        result = _make_result(
            ml_prediction={
                "predicted_label": "LAG",
                "confidence": 0.75,
                "probabilities": {"COUPLING": 0.1, "LAG": 0.75, "NOISE": 0.15},
                "model_version": "2026-03-03T00:00:00+00:00",
                "calibrated": True,
            }
        )
        d = dataclasses.asdict(result)
        # Must be JSON-serialisable (baseline_status is None, so no issue)
        d.pop("baseline_status", None)
        raw = json.dumps(d)
        parsed = json.loads(raw)
        assert parsed["ml_prediction"]["predicted_label"] == "LAG"


# ---------------------------------------------------------------------------
# _run_ml_inference()
# ---------------------------------------------------------------------------


class TestRunMlInference:
    def test_empty_features_returns_unchanged(self):
        result = _make_result()
        new_result = _run_ml_inference(result, {})
        assert new_result.ml_prediction is None
        assert new_result is result  # same object

    def test_returns_unchanged_when_no_model(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        monkeypatch.setattr(clf, "load_model", lambda: None)
        result = _make_result()
        features = {"ts": 1.0, "convergence_event_count": 2}
        new_result = _run_ml_inference(result, features)
        assert new_result.ml_prediction is None

    def test_populates_ml_prediction_when_model_available(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        fake_pred = _make_fake_prediction("COUPLING")
        monkeypatch.setattr(clf, "load_model", lambda: object())  # truthy sentinel
        monkeypatch.setattr(clf, "predict", lambda _features: fake_pred)

        result = _make_result()
        features = {"ts": 1.0, "convergence_event_count": 4}
        new_result = _run_ml_inference(result, features)
        assert new_result.ml_prediction is not None
        assert new_result.ml_prediction["predicted_label"] == "COUPLING"

    def test_ml_prediction_has_all_expected_keys(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        monkeypatch.setattr(clf, "load_model", lambda: object())
        monkeypatch.setattr(clf, "predict", lambda _: _make_fake_prediction())

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        pred = new_result.ml_prediction
        assert pred is not None
        for key in (
            "predicted_label",
            "confidence",
            "probabilities",
            "model_version",
            "calibrated",
        ):
            assert key in pred, f"missing key: {key}"

    def test_confidence_in_zero_one(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        monkeypatch.setattr(clf, "load_model", lambda: object())
        monkeypatch.setattr(clf, "predict", lambda _: _make_fake_prediction())

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        assert 0.0 <= new_result.ml_prediction["confidence"] <= 1.0

    def test_predicted_label_is_valid(self, monkeypatch):
        import signal_core.core.ml.classifier as clf
        from signal_core.core.ml.classifier import LABEL_MAP

        monkeypatch.setattr(clf, "load_model", lambda: object())
        monkeypatch.setattr(clf, "predict", lambda _: _make_fake_prediction("LAG"))

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        assert new_result.ml_prediction["predicted_label"] in LABEL_MAP

    def test_returns_unchanged_when_predict_raises(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        monkeypatch.setattr(clf, "load_model", lambda: object())
        monkeypatch.setattr(
            clf,
            "predict",
            lambda _: (_ for _ in ()).throw(RuntimeError("model corrupt")),
        )

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        # Exception is swallowed — result is unchanged
        assert new_result.ml_prediction is None

    def test_returns_unchanged_when_load_model_raises(self, monkeypatch):
        import signal_core.core.ml.classifier as clf

        def _raising_load():
            raise OSError("disk error")

        monkeypatch.setattr(clf, "load_model", _raising_load)

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        assert new_result.ml_prediction is None

    def test_original_result_not_mutated(self, monkeypatch):
        """_run_ml_inference must use dataclasses.replace, not mutate in place."""
        import signal_core.core.ml.classifier as clf

        monkeypatch.setattr(clf, "load_model", lambda: object())
        monkeypatch.setattr(clf, "predict", lambda _: _make_fake_prediction())

        result = _make_result()
        new_result = _run_ml_inference(result, {"ts": 1.0})
        # Original is unchanged
        assert result.ml_prediction is None
        # New result has prediction
        assert new_result.ml_prediction is not None
