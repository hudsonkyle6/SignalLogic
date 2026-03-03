"""
ML Calibration Audit — reliability diagnostics for the classifier.
POSTURE: OBSERVATORY (read-only from model + labels + features)

Evaluates whether the calibrated probabilities produced by classifier.py
are actually trustworthy, not just accurate.  A model can predict the right
class 90% of the time but still assign overconfident probabilities (e.g. 98%
when it should be 85%).  For a high-stakes operator tool, miscalibrated
confidence is as dangerous as a wrong prediction.

Metrics computed:
    Brier score     Multi-class mean squared error of probability vectors.
                    Range [0, 2].  Perfect=0, uninformed (uniform)=4/3.
    Log-loss        Cross-entropy.  Perfect=0, uninformed (uniform)≈log(3).
    ECE             Expected Calibration Error — weighted mean |conf - acc|
                    across confidence bins.  Perfect=0.  < 0.05 is excellent.
    MCE             Maximum Calibration Error — worst single bin.
    Reliability     Per-bin table: confidence bucket → actual accuracy.
                    A perfectly calibrated model lies on the diagonal.

Note: metrics are computed on the full labelled dataset using the final
fitted model (in-sample evaluation).  The out-of-sample CV accuracy from
classifier.py --evaluate is a more conservative estimate of generalisation
performance.  This audit focuses on calibration quality of the probabilities,
not classification accuracy.

Usage (CLI):
    python -m signal_core.core.ml.calibration_audit

    # Custom bin count
    python -m signal_core.core.ml.calibration_audit --bins 5

    # Export to JSON for plotting
    python -m signal_core.core.ml.calibration_audit --json

Authority:
    READ-ONLY from data/ml/model.joblib, data/ml/features.jsonl,
                    data/ml/labels.jsonl, data/ml/model_meta.json
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
from sklearn.metrics import log_loss

from signal_core.core.log import get_logger
from signal_core.core.ml.classifier import (
    MIN_SAMPLES,
    LABEL_MAP,
    _build_feature_matrix,
    _load_paired,
    load_model,
    model_info,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class CalibrationResult:
    n_samples: int
    brier_score: float  # multi-class MSE of proba vectors, range [0, 2]
    log_loss_value: float  # cross-entropy (nats), lower = better
    ece: float  # expected calibration error, range [0, 1]
    mce: float  # maximum calibration error, range [0, 1]
    per_class_brier: Dict[str, float]  # {COUPLING/LAG/NOISE: brier}
    reliability_bins: List[Dict]  # [{low, high, n, confidence, accuracy, gap}]
    model_version: str  # trained_at_iso from model_meta
    audited_at: float  # unix timestamp when audit was run
    n_bins: int  # number of bins used


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def _brier_multiclass(proba: np.ndarray, y: np.ndarray) -> float:
    """
    Multi-class Brier score: mean over samples of sum_c (p_c - y_c)^2.
    Range [0, 2].  Perfect = 0.  Uniform random (3 classes) = 4/3 ≈ 1.333.
    """
    n = len(y)
    Y = np.zeros((n, len(LABEL_MAP)), dtype=np.float32)
    for i, yi in enumerate(y):
        Y[i, yi] = 1.0
    return float(np.mean(np.sum((proba - Y) ** 2, axis=1)))


def _per_class_brier(proba: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """
    One-vs-rest Brier score for each class.
    Measures how well each class's probability is individually calibrated.
    Range [0, 1] per class.
    """
    result = {}
    for label, idx in sorted(LABEL_MAP.items()):
        y_binary = (y == idx).astype(np.float32)
        p_class = proba[:, idx]
        result[label] = round(float(np.mean((p_class - y_binary) ** 2)), 4)
    return result


def _reliability_bins(
    proba: np.ndarray, y: np.ndarray, n_bins: int
) -> tuple[float, float, List[Dict]]:
    """
    Top-label reliability diagram data.

    For each confidence bin [low, high]:
      confidence = mean of max(proba) for samples in bin
      accuracy   = fraction of samples where the top prediction is correct
      gap        = |confidence - accuracy|

    ECE = sum_b (n_b / n) * gap_b
    MCE = max_b gap_b

    Returns (ece, mce, bins).
    """
    top_conf = np.max(proba, axis=1)  # shape (n,)
    correct = (np.argmax(proba, axis=1) == y).astype(np.float32)
    n = len(y)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    bins: List[Dict] = []

    for b in range(n_bins):
        low, high = float(edges[b]), float(edges[b + 1])
        if b < n_bins - 1:
            mask = (top_conf >= low) & (top_conf < high)
        else:
            mask = (top_conf >= low) & (top_conf <= high)

        n_b = int(mask.sum())
        if n_b == 0:
            continue

        conf_b = float(top_conf[mask].mean())
        acc_b = float(correct[mask].mean())
        gap = abs(conf_b - acc_b)
        ece += (n_b / n) * gap
        mce = max(mce, gap)
        bins.append(
            {
                "low": round(low, 2),
                "high": round(high, 2),
                "n": n_b,
                "confidence": round(conf_b, 4),
                "accuracy": round(acc_b, 4),
                "gap": round(gap, 4),
            }
        )

    return round(ece, 4), round(mce, 4), bins


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_calibration(n_bins: int = 10) -> CalibrationResult:
    """
    Compute calibration metrics for the saved model against all labelled data.

    Loads the saved model (must exist) and the paired (feature, label) dataset,
    runs predict_proba on every labelled cycle, and computes Brier score,
    log-loss, ECE, MCE, and a reliability curve.

    Raises:
        RuntimeError: if no trained model exists (run classifier --train first)
        ValueError:   if fewer than MIN_SAMPLES labelled cycles are available
    """
    model = load_model()
    if model is None:
        raise RuntimeError(
            "No trained model found. "
            "Run: python -m signal_core.core.ml.classifier --train"
        )

    meta = model_info()
    assert meta is not None

    paired_features, paired_labels = _load_paired()
    n = len(paired_features)
    if n < MIN_SAMPLES:
        raise ValueError(
            f"Only {n} labelled cycles; need at least {MIN_SAMPLES} to audit."
        )

    feature_cols = meta["feature_cols"]
    X, _ = _build_feature_matrix(paired_features, feature_cols=feature_cols)
    y = np.array([LABEL_MAP[rec["label"]] for rec in paired_labels], dtype=np.int32)

    proba = model.predict_proba(X)  # shape (n, 3)

    brier = _brier_multiclass(proba, y)
    ll = float(log_loss(y, proba))
    per_class = _per_class_brier(proba, y)
    ece, mce, bins = _reliability_bins(proba, y, n_bins)

    log.info(
        "calibration audit n=%d brier=%.4f log_loss=%.4f ece=%.4f mce=%.4f",
        n,
        brier,
        ll,
        ece,
        mce,
    )

    return CalibrationResult(
        n_samples=n,
        brier_score=round(brier, 4),
        log_loss_value=round(ll, 4),
        ece=ece,
        mce=mce,
        per_class_brier=per_class,
        reliability_bins=bins,
        model_version=meta.get("trained_at_iso", "unknown"),
        audited_at=time.time(),
        n_bins=n_bins,
    )


# ---------------------------------------------------------------------------
# Reference values for interpretation
# ---------------------------------------------------------------------------

# For a uniformly random 3-class classifier using sum_c (p_c - y_c)^2:
#   Per sample: (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = 4/9 + 1/9 + 1/9 = 2/3
#   Brier = 2/3 ≈ 0.667   Log-loss = log(3) ≈ 1.099
_RANDOM_BRIER = round(2 / 3, 4)
_RANDOM_LOGLOSS = round(float(np.log(len(LABEL_MAP))), 4)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="SignalLogic ML — calibration audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
interpretation:
  Brier score  < 0.10 excellent  0.10–0.20 good  0.20–0.33 fair  > 0.33 random
  Log-loss     < 0.30 excellent  0.30–0.60 good  > 1.10 ≈ random (3-class)
  ECE          < 0.05 excellent  0.05–0.10 acceptable  > 0.10 recalibrate

reference (uniformly random classifier):
  Brier ≈ 1.333    Log-loss ≈ 1.099
""",
    )
    ap.add_argument("--bins", type=int, default=10, help="Number of reliability bins")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    args = ap.parse_args()

    try:
        result = compute_calibration(n_bins=args.bins)
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    if args.json:
        from dataclasses import asdict

        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return

    ts_str = datetime.fromtimestamp(result.audited_at, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    print(f"\nCalibration Audit — {result.n_samples} samples   [{ts_str}]")
    print(f"Model: {result.model_version}")
    print()
    print(f"  Brier score : {result.brier_score:.4f}   (random ≈ {_RANDOM_BRIER})")
    print(f"  Log-loss    : {result.log_loss_value:.4f}   (random ≈ {_RANDOM_LOGLOSS})")
    print(f"  ECE         : {result.ece:.4f}   (perfect = 0)")
    print(f"  MCE         : {result.mce:.4f}")
    print()
    print("  Per-class Brier (one-vs-rest):")
    for label, bs in sorted(result.per_class_brier.items()):
        bar = "▓" * int(bs * 40)
        print(f"    {label:<10} {bs:.4f}  {bar}")
    print()
    print(f"  {'Bin':<12} {'N':>5}  {'Confidence':>12}  {'Accuracy':>10}  {'Gap':>8}")
    print(f"  {'-' * 12} {'-' * 5}  {'-' * 12}  {'-' * 10}  {'-' * 8}")
    for b in result.reliability_bins:
        arrow = "▲" if b["confidence"] > b["accuracy"] else "▼"
        print(
            f"  [{b['low']:.1f}–{b['high']:.1f}]   {b['n']:>5}  "
            f"{b['confidence']:.4f}       {b['accuracy']:.4f}    "
            f"{arrow} {b['gap']:.4f}"
        )
    print()
    if result.ece < 0.05:
        verdict = "EXCELLENT — probabilities are reliable for operator decisions"
    elif result.ece < 0.10:
        verdict = "ACCEPTABLE — minor calibration drift; monitor as labels grow"
    else:
        verdict = "RECALIBRATE — run --train with more labelled data"
    print(f"  Verdict: {verdict}")
    print()


if __name__ == "__main__":
    main()
