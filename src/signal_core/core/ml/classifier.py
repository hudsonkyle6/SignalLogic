"""
ML Classifier — XGBoost convergence event classifier.
POSTURE: TRAIN (writes model files) | OBSERVATORY (predict/evaluate/info)

Trains an XGBoost multi-class classifier on operator-labelled feature
vectors from data/ml/features.jsonl + data/ml/labels.jsonl.

Requires the [ml] optional dependency group:
    pip install "signal-logic[ml]"

Produces:
    data/ml/model.joblib     — fitted CalibratedClassifierCV (XGBoost + isotonic)
    data/ml/model_meta.json  — feature columns, label map, trained_at, CV metrics

TRAINING GATE: minimum 200 labelled cycles required.  Below this, the
classifier refuses to train — a cold, underfitted model is worse than no
model in a high-stakes context.

Label encoding (alphabetical, stable):
    COUPLING → 0    LAG → 1    NOISE → 2

Usage (CLI):
    # Train and save model (requires >= 200 labelled cycles)
    python -m signal_core.core.ml.classifier --train

    # Evaluate via 5-fold stratified CV (read-only, no model saved)
    python -m signal_core.core.ml.classifier --evaluate

    # Predict for a cycle from features.jsonl
    python -m signal_core.core.ml.classifier --predict --ts 1741000000.0

    # Show current model metadata
    python -m signal_core.core.ml.classifier --info

Authority:
    --train:    WRITE to data/ml/model.joblib, data/ml/model_meta.json
    --evaluate: READ-ONLY
    --predict:  READ-ONLY
    --info:     READ-ONLY
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from xgboost import XGBClassifier

from rhythm_os.runtime.paths import ML_DIR
from signal_core.core.log import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FEATURES_PATH = ML_DIR / "features.jsonl"
_LABELS_PATH = ML_DIR / "labels.jsonl"
_MODEL_PATH = ML_DIR / "model.joblib"
_META_PATH = ML_DIR / "model_meta.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SAMPLES = 200
N_FOLDS = 5
IMBALANCE_WARN_PCT = 10.0  # warn if any class < this % of total

# Stable alphabetical label encoding — do not change without retraining
LABEL_MAP: Dict[str, int] = {"COUPLING": 0, "LAG": 1, "NOISE": 2}
LABEL_INV: Dict[int, str] = {v: k for k, v in LABEL_MAP.items()}

# Keys present in every feature record that are NOT model inputs
_NON_FEATURE_KEYS = frozenset({"ts"})

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class Prediction:
    ts: float
    predicted_label: str  # NOISE | COUPLING | LAG
    confidence: float  # probability of predicted class
    probabilities: Dict[str, float]  # {NOISE: x, COUPLING: y, LAG: z}
    model_version: str  # trained_at from meta (ISO-8601 string)
    calibrated: bool  # True — isotonic regression applied


@dataclass
class TrainResult:
    model_path: Path
    meta_path: Path
    n_samples: int
    n_features: int
    label_counts: Dict[str, int]
    cv_accuracy: float
    cv_f1_weighted: float
    per_class: Dict[str, Dict[str, float]]  # {label: {precision, recall, f1}}
    trained_at: float


@dataclass
class EvalResult:
    n_samples: int
    n_features: int
    label_counts: Dict[str, int]
    accuracy: float
    f1_weighted: float
    per_class: Dict[str, Dict[str, float]]
    n_folds: int


# ---------------------------------------------------------------------------
# Module-level model cache (populated on first predict call)
# ---------------------------------------------------------------------------

_MODEL_CACHE: Optional[CalibratedClassifierCV] = None
_META_CACHE: Optional[dict] = None


def _invalidate_cache() -> None:
    global _MODEL_CACHE, _META_CACHE
    _MODEL_CACHE = None
    _META_CACHE = None


# ---------------------------------------------------------------------------
# File loading helpers
# ---------------------------------------------------------------------------


def _load_features() -> List[dict]:
    if not _FEATURES_PATH.exists():
        return []
    records = []
    for line in _FEATURES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def _load_labels() -> Dict[float, dict]:
    """Return labels keyed by ts as plain dicts."""
    if not _LABELS_PATH.exists():
        return {}
    labels: Dict[float, dict] = {}
    for line in _LABELS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            labels[float(rec["ts"])] = rec
        except Exception:
            continue
    return labels


def _load_paired() -> Tuple[List[dict], List[dict]]:
    """
    Inner-join feature records and label records on ts.

    Returns (feature_list, label_list) in matched order.  Only cycles
    that have BOTH a feature record AND an operator label are included.
    """
    features_by_ts = {float(rec["ts"]): rec for rec in _load_features() if "ts" in rec}
    labels = _load_labels()

    paired_features: List[dict] = []
    paired_labels: List[dict] = []
    for ts, label_rec in sorted(labels.items()):
        if ts in features_by_ts:
            paired_features.append(features_by_ts[ts])
            paired_labels.append(label_rec)

    return paired_features, paired_labels


# ---------------------------------------------------------------------------
# Feature matrix construction
# ---------------------------------------------------------------------------


def _build_feature_matrix(
    feature_records: List[dict],
    feature_cols: Optional[List[str]] = None,
) -> Tuple[np.ndarray, List[str]]:
    """
    Build a float32 feature matrix from a list of feature dicts.

    Training mode (feature_cols=None):
        Infers columns from the union of all keys across all records,
        excluding _NON_FEATURE_KEYS.  Returns the sorted column list.

    Inference mode (feature_cols provided):
        Uses the exact saved column ordering.  Missing keys default to 0.0;
        extra keys in the record are silently ignored.  A warning is logged
        when keys are present in the record but absent from the saved schema
        (may indicate new domains added after training).
    """
    if feature_cols is None:
        col_set: set = set()
        for rec in feature_records:
            col_set.update(k for k in rec if k not in _NON_FEATURE_KEYS)
        feature_cols = sorted(col_set)

    col_idx = {col: i for i, col in enumerate(feature_cols)}
    X = np.zeros((len(feature_records), len(feature_cols)), dtype=np.float32)

    for row, rec in enumerate(feature_records):
        # Warn once if the record has keys not in the saved schema
        unknown = [k for k in rec if k not in _NON_FEATURE_KEYS and k not in col_idx]
        if unknown:
            log.warning(
                "classifier inference: %d feature key(s) not in saved schema "
                "(new domain?): %s",
                len(unknown),
                unknown[:5],
            )
        for col, idx in col_idx.items():
            val = rec.get(col, 0.0)
            if isinstance(val, bool):
                val = int(val)
            X[row, idx] = float(val)

    return X, feature_cols


# ---------------------------------------------------------------------------
# XGBoost estimator factory
# ---------------------------------------------------------------------------


def _make_estimator() -> XGBClassifier:
    """
    Build the base XGBClassifier with conservative hyperparameters tuned
    for small datasets (200–2000 samples).

    Calibration is handled externally by CalibratedClassifierCV so the
    base estimator does not need to emit calibrated probabilities itself.
    """
    return XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="multi:softprob",
        num_class=len(LABEL_MAP),
        random_state=42,
        n_jobs=1,  # deterministic, no race conditions
        eval_metric="mlogloss",
        verbosity=0,
    )


def _make_calibrated() -> CalibratedClassifierCV:
    """Wrap XGBClassifier in isotonic-regression calibration."""
    return CalibratedClassifierCV(
        estimator=_make_estimator(),
        cv=N_FOLDS,
        method="isotonic",
    )


# ---------------------------------------------------------------------------
# Class-imbalance check
# ---------------------------------------------------------------------------


def _check_imbalance(label_counts: Dict[str, int], n_total: int) -> None:
    for label, count in label_counts.items():
        pct = count / n_total * 100
        if pct < IMBALANCE_WARN_PCT:
            log.warning(
                "class imbalance: %s has only %d samples (%.1f%% of total). "
                "Consider collecting more %s cycles before training.",
                label,
                count,
                pct,
                label,
            )


# ---------------------------------------------------------------------------
# CV evaluation helper
# ---------------------------------------------------------------------------


def _run_cv(
    X: np.ndarray, y: np.ndarray
) -> Tuple[float, float, Dict[str, Dict[str, float]]]:
    """
    Run N_FOLDS-fold stratified cross-validation using out-of-fold predictions.

    Returns (accuracy, f1_weighted, per_class_metrics).

    We use cross_val_predict (not cross_validate) so we can compute the full
    classification_report from OOF predictions — giving per-class precision,
    recall, and F1 that the operator can act on.

    Note: CV folds use unweighted class-balanced splitting.  Sample weights
    are applied only on the final full-dataset model fit in train(), where
    they have the most impact.  Using weights in OOF folds would require
    sklearn metadata routing configuration that varies by sklearn version;
    omitting them here keeps the CV path version-stable.
    """
    cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    oof_pred = cross_val_predict(
        _make_calibrated(),
        X,
        y,
        cv=cv,
        method="predict",
    )

    report = classification_report(
        y,
        oof_pred,
        target_names=sorted(LABEL_MAP, key=lambda k: LABEL_MAP[k]),
        output_dict=True,
        zero_division=0,
    )

    accuracy = float(report.get("accuracy", 0.0))
    f1_weighted = float(report.get("weighted avg", {}).get("f1-score", 0.0))

    per_class: Dict[str, Dict[str, float]] = {}
    for label in LABEL_MAP:
        row = report.get(label, {})
        per_class[label] = {
            "precision": round(float(row.get("precision", 0.0)), 4),
            "recall": round(float(row.get("recall", 0.0)), 4),
            "f1": round(float(row.get("f1-score", 0.0)), 4),
            "support": int(row.get("support", 0)),
        }

    return round(accuracy, 4), round(f1_weighted, 4), per_class


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def train(min_samples: int = MIN_SAMPLES) -> TrainResult:
    """
    Train the XGBoost classifier on all labelled cycles and save the model.

    Steps:
        1. Load paired (feature, label) records
        2. Enforce min_samples gate
        3. Warn on class imbalance
        4. Build feature matrix X, label vector y, weight vector w
        5. Run 5-fold OOF CV for metrics (nothing saved)
        6. Train final CalibratedClassifierCV on full dataset
        7. Save model.joblib + model_meta.json

    Raises:
        ValueError: if fewer than min_samples labelled cycles exist
        ImportError: if xgboost / sklearn / joblib are not installed
    """
    paired_features, paired_labels = _load_paired()
    n = len(paired_features)

    if n < min_samples:
        raise ValueError(
            f"Only {n} labelled cycles available; need at least {min_samples}. "
            f"Label more cycles with: python -m signal_core.core.ml.outcome_log --list-unlabelled"
        )

    label_counts = {lbl: 0 for lbl in LABEL_MAP}
    for rec in paired_labels:
        label_counts[rec["label"]] = label_counts.get(rec["label"], 0) + 1

    _check_imbalance(label_counts, n)

    X, feature_cols = _build_feature_matrix(paired_features)
    y = np.array([LABEL_MAP[rec["label"]] for rec in paired_labels], dtype=np.int32)
    weights = np.array(
        [float(rec.get("weight", 1.0)) for rec in paired_labels], dtype=np.float32
    )

    log.info(
        "classifier training: n=%d features=%d classes=%s",
        n,
        len(feature_cols),
        label_counts,
    )

    # CV metrics (OOF, read-only — no model is saved from these folds)
    cv_accuracy, cv_f1_weighted, per_class = _run_cv(X, y)
    log.info(
        "classifier CV: accuracy=%.4f f1_weighted=%.4f", cv_accuracy, cv_f1_weighted
    )

    # Final model trained on full dataset
    model = _make_calibrated()
    model.fit(X, y, sample_weight=weights)

    # Persist
    ML_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _MODEL_PATH)

    trained_at = time.time()
    meta = {
        "feature_cols": feature_cols,
        "label_map": LABEL_MAP,
        "trained_at": trained_at,
        "trained_at_iso": datetime.fromtimestamp(
            trained_at, tz=timezone.utc
        ).isoformat(),
        "n_samples": n,
        "n_features": len(feature_cols),
        "label_counts": label_counts,
        "cv_accuracy": cv_accuracy,
        "cv_f1_weighted": cv_f1_weighted,
        "per_class": per_class,
        "n_folds": N_FOLDS,
    }
    _META_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    _invalidate_cache()
    log.info("classifier saved model=%s meta=%s", _MODEL_PATH, _META_PATH)

    return TrainResult(
        model_path=_MODEL_PATH,
        meta_path=_META_PATH,
        n_samples=n,
        n_features=len(feature_cols),
        label_counts=label_counts,
        cv_accuracy=cv_accuracy,
        cv_f1_weighted=cv_f1_weighted,
        per_class=per_class,
        trained_at=trained_at,
    )


def evaluate(n_folds: int = N_FOLDS) -> EvalResult:
    """
    Evaluate via stratified k-fold CV without saving any model.

    Use this to check model quality before committing to --train.
    Returns EvalResult with accuracy, weighted F1, and per-class breakdown.

    Raises:
        ValueError: if fewer than MIN_SAMPLES labelled cycles exist
    """
    paired_features, paired_labels = _load_paired()
    n = len(paired_features)

    if n < MIN_SAMPLES:
        raise ValueError(
            f"Only {n} labelled cycles; need at least {MIN_SAMPLES} to evaluate."
        )

    label_counts = {lbl: 0 for lbl in LABEL_MAP}
    for rec in paired_labels:
        label_counts[rec["label"]] = label_counts.get(rec["label"], 0) + 1

    _check_imbalance(label_counts, n)

    X, feature_cols = _build_feature_matrix(paired_features)
    y = np.array([LABEL_MAP[rec["label"]] for rec in paired_labels], dtype=np.int32)

    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    oof_pred = cross_val_predict(
        _make_calibrated(),
        X,
        y,
        cv=cv,
        method="predict",
    )

    report = classification_report(
        y,
        oof_pred,
        target_names=sorted(LABEL_MAP, key=lambda k: LABEL_MAP[k]),
        output_dict=True,
        zero_division=0,
    )

    accuracy = round(float(report.get("accuracy", 0.0)), 4)
    f1_weighted = round(float(report.get("weighted avg", {}).get("f1-score", 0.0)), 4)

    per_class: Dict[str, Dict[str, float]] = {}
    for label in LABEL_MAP:
        row = report.get(label, {})
        per_class[label] = {
            "precision": round(float(row.get("precision", 0.0)), 4),
            "recall": round(float(row.get("recall", 0.0)), 4),
            "f1": round(float(row.get("f1-score", 0.0)), 4),
            "support": int(row.get("support", 0)),
        }

    return EvalResult(
        n_samples=n,
        n_features=len(feature_cols),
        label_counts=label_counts,
        accuracy=accuracy,
        f1_weighted=f1_weighted,
        per_class=per_class,
        n_folds=n_folds,
    )


def load_model() -> Optional[CalibratedClassifierCV]:
    """
    Load the saved model from disk (cached after first call).

    Returns None if no model has been trained yet.
    """
    global _MODEL_CACHE, _META_CACHE

    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    if not _MODEL_PATH.exists():
        return None
    if not _META_PATH.exists():
        log.warning("model.joblib found but model_meta.json missing — skipping load")
        return None

    _MODEL_CACHE = joblib.load(_MODEL_PATH)
    _META_CACHE = json.loads(_META_PATH.read_text(encoding="utf-8"))
    log.info(
        "classifier loaded trained_at=%s n_samples=%d",
        _META_CACHE.get("trained_at_iso", "?"),
        _META_CACHE.get("n_samples", 0),
    )
    return _MODEL_CACHE


def model_info() -> Optional[dict]:
    """
    Return model metadata (from model_meta.json), or None if no model exists.

    Triggers a model load if the cache is cold, but does NOT raise if the
    model is missing — returns None instead so callers can check gracefully.
    """
    global _META_CACHE

    if _META_CACHE is not None:
        return _META_CACHE

    if not _META_PATH.exists():
        return None

    _META_CACHE = json.loads(_META_PATH.read_text(encoding="utf-8"))
    return _META_CACHE


def predict(feature_dict: Dict[str, Any]) -> Prediction:
    """
    Predict the convergence event label for a single feature dict.

    The feature dict must have the same schema as feature_builder records
    (dynamic domain keys are supported — missing columns default to 0.0).

    Raises:
        RuntimeError: if no trained model exists (run --train first)
    """
    model = load_model()
    if model is None:
        raise RuntimeError(
            "No trained model found. Run: python -m signal_core.core.ml.classifier --train"
        )

    meta = model_info()
    assert meta is not None  # guaranteed since load_model populated it

    feature_cols: List[str] = meta["feature_cols"]
    X, _ = _build_feature_matrix([feature_dict], feature_cols=feature_cols)

    proba = model.predict_proba(X)[0]  # shape: (n_classes,)
    pred_idx = int(np.argmax(proba))
    predicted_label = LABEL_INV[pred_idx]
    confidence = round(float(proba[pred_idx]), 4)

    probabilities = {LABEL_INV[i]: round(float(p), 4) for i, p in enumerate(proba)}

    return Prediction(
        ts=float(feature_dict.get("ts", 0.0)),
        predicted_label=predicted_label,
        confidence=confidence,
        probabilities=probabilities,
        model_version=meta.get("trained_at_iso", "unknown"),
        calibrated=True,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_eval(
    label_counts: Dict[str, int],
    n_samples: int,
    n_features: int,
    accuracy: float,
    f1_weighted: float,
    per_class: Dict[str, Dict[str, float]],
    n_folds: int,
) -> None:
    print(f"\n  Samples : {n_samples}  Features: {n_features}  CV folds: {n_folds}")
    print(f"  Accuracy: {accuracy:.1%}   Weighted F1: {f1_weighted:.1%}\n")
    print(f"  {'Label':<12} {'Precision':>10} {'Recall':>8} {'F1':>8} {'Support':>9}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 9}")
    for label in sorted(LABEL_MAP):
        m = per_class.get(label, {})
        print(
            f"  {label:<12} {m.get('precision', 0):.4f}     "
            f"{m.get('recall', 0):.4f}   {m.get('f1', 0):.4f}   "
            f"{m.get('support', 0):>7}"
        )
    print()


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="SignalLogic ML — XGBoost convergence classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Train and save model (needs >= 200 labelled cycles)
  python -m signal_core.core.ml.classifier --train

  # Evaluate via 5-fold CV without saving
  python -m signal_core.core.ml.classifier --evaluate

  # Predict for a cycle
  python -m signal_core.core.ml.classifier --predict --ts 1741000000.0

  # Show model info
  python -m signal_core.core.ml.classifier --info
""",
    )
    ap.add_argument("--train", action="store_true", help="Train and save model")
    ap.add_argument(
        "--evaluate", action="store_true", help="5-fold CV evaluation (no model saved)"
    )
    ap.add_argument("--predict", action="store_true", help="Predict for a cycle")
    ap.add_argument("--ts", type=float, help="Cycle timestamp for --predict")
    ap.add_argument("--info", action="store_true", help="Show current model metadata")
    args = ap.parse_args()

    if args.info:
        meta = model_info()
        if meta is None:
            print("No trained model found. Run --train first.")
            return
        print(f"\nModel trained:   {meta.get('trained_at_iso', '?')}")
        print(f"Samples:         {meta.get('n_samples', 0)}")
        print(f"Features:        {meta.get('n_features', 0)}")
        print(f"CV accuracy:     {meta.get('cv_accuracy', 0):.1%}")
        print(f"CV F1 (weighted):{meta.get('cv_f1_weighted', 0):.1%}")
        print(f"\nLabel counts:    {meta.get('label_counts', {})}")
        print(f"CV folds:        {meta.get('n_folds', N_FOLDS)}")
        return

    if args.train:
        try:
            result = train()
        except ValueError as e:
            print(f"Error: {e}")
            raise SystemExit(1)
        print(f"\nModel saved: {result.model_path}")
        _print_eval(
            result.label_counts,
            result.n_samples,
            result.n_features,
            result.cv_accuracy,
            result.cv_f1_weighted,
            result.per_class,
            N_FOLDS,
        )
        return

    if args.evaluate:
        try:
            result = evaluate()
        except ValueError as e:
            print(f"Error: {e}")
            raise SystemExit(1)
        print("\n[Evaluate — 5-fold CV, no model saved]")
        _print_eval(
            result.label_counts,
            result.n_samples,
            result.n_features,
            result.accuracy,
            result.f1_weighted,
            result.per_class,
            result.n_folds,
        )
        return

    if args.predict:
        if not args.ts:
            ap.error("--predict requires --ts <timestamp>")
        # Load the feature record from features.jsonl
        features = _load_features()
        matched = [f for f in features if float(f.get("ts", -1)) == args.ts]
        if not matched:
            print(f"Error: no feature record found for ts={args.ts}")
            raise SystemExit(1)
        try:
            pred = predict(matched[0])
        except RuntimeError as e:
            print(f"Error: {e}")
            raise SystemExit(1)
        ts_str = datetime.fromtimestamp(pred.ts, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        print(f"\nts={pred.ts:.0f}  {ts_str}")
        print(
            f"Prediction:  {pred.predicted_label}  (confidence {pred.confidence:.1%})"
        )
        print(f"Calibrated:  {pred.calibrated}")
        print(f"Model:       {pred.model_version}")
        print(f"Proba:       {pred.probabilities}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
