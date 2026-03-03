"""
ML Outcome Log — operator label collection for classifier training.
POSTURE: WRITE (labels only — never touches feature records)

The operator reviews cycle outputs (dashboard, convergence summary, scar
state) and assigns a ground-truth label to each convergence event cycle.
Labels are written to data/ml/labels.jsonl and matched to feature records
by their cycle timestamp (ts).  These paired records are the training set
for the XGBoost classifier.

Valid labels (what the convergence event actually was):
    NOISE     — coincidental phase overlap, no structural relationship
    COUPLING  — domains are structurally linked (correlated signal)
    LAG       — one domain consistently leads another (temporal offset)

Valid outcomes (what the operator chose to do):
    ACTED      — took an action based on the signal
    HELD       — consciously held position / did not act
    MONITORED  — watched without committing either way

Weight controls training emphasis.  Default 1.0.  Use 2.0 for high-
confidence labels or when overriding a model recommendation — these are
the most informative training samples for a high-stakes classifier.

Usage (CLI):
    # Label a specific cycle
    python -m signal_core.core.ml.outcome_log \\
        --ts 1741000000.0 --label COUPLING --outcome ACTED

    # Add notes and override weight
    python -m signal_core.core.ml.outcome_log \\
        --ts 1741000000.0 --label NOISE --outcome HELD \\
        --notes "system scar was residual from yesterday" --weight 2.0

    # Show recent unlabelled cycles with feature context for review
    python -m signal_core.core.ml.outcome_log --list-unlabelled --limit 10

    # Show label distribution and coverage stats
    python -m signal_core.core.ml.outcome_log --stats

Authority:
    - WRITE to data/ml/labels.jsonl only
    - READ from data/ml/features.jsonl (validation + coverage reporting)
    - Never modifies feature records
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from rhythm_os.runtime.paths import ML_DIR
from signal_core.core.log import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_LABELS = frozenset({"NOISE", "COUPLING", "LAG"})
VALID_OUTCOMES = frozenset({"ACTED", "HELD", "MONITORED"})

_FEATURES_PATH = ML_DIR / "features.jsonl"
_LABELS_PATH = ML_DIR / "labels.jsonl"


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class OutcomeRecord:
    ts: float  # matches feature record ts exactly
    label: str  # NOISE | COUPLING | LAG
    outcome: str  # ACTED | HELD | MONITORED
    notes: str  # free text (empty string if omitted)
    labelled_at: float  # unix timestamp when this label was written
    weight: float  # training weight (1.0 default, 2.0 for high-confidence)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OutcomeRecord":
        return cls(
            ts=float(d["ts"]),
            label=str(d["label"]),
            outcome=str(d["outcome"]),
            notes=str(d.get("notes", "")),
            labelled_at=float(d.get("labelled_at", 0.0)),
            weight=float(d.get("weight", 1.0)),
        )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _load_labels() -> Dict[float, OutcomeRecord]:
    """Load all labels keyed by ts.  Skips corrupt lines."""
    labels: Dict[float, OutcomeRecord] = {}
    if not _LABELS_PATH.exists():
        return labels
    for line in _LABELS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            labels[float(json.loads(line)["ts"])] = OutcomeRecord.from_dict(
                json.loads(line)
            )
        except Exception:
            continue
    return labels


def _save_labels(labels: Dict[float, OutcomeRecord]) -> None:
    """Full rewrite of labels.jsonl (labels are small — O(labelled cycles))."""
    ML_DIR.mkdir(parents=True, exist_ok=True)
    with _LABELS_PATH.open("w", encoding="utf-8") as f:
        for rec in sorted(labels.values(), key=lambda r: r.ts):
            f.write(
                json.dumps(rec.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
            )


def _load_features() -> List[dict]:
    """Load all feature records from features.jsonl.  Skips corrupt lines."""
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(label: str, outcome: str) -> None:
    """Raise ValueError if label or outcome is not in the valid sets."""
    if label not in VALID_LABELS:
        raise ValueError(
            f"Invalid label {label!r}. Must be one of: {sorted(VALID_LABELS)}"
        )
    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"Invalid outcome {outcome!r}. Must be one of: {sorted(VALID_OUTCOMES)}"
        )


def _find_feature(ts: float) -> Optional[dict]:
    """Return the feature record for ts, or None if not found."""
    for rec in _load_features():
        if float(rec.get("ts", -1)) == ts:
            return rec
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_label(
    ts: float,
    label: str,
    outcome: str,
    notes: str = "",
    weight: float = 1.0,
) -> OutcomeRecord:
    """
    Write a ground-truth label for a specific cycle.

    Validates that ts matches a known feature record — operators must
    label cycles the system has actually observed.  Overwrites any
    existing label for the same ts (last write wins).

    Raises:
        ValueError: if label/outcome is invalid or ts has no feature record.
    """
    _validate(label, outcome)

    feature = _find_feature(ts)
    if feature is None:
        raise ValueError(
            f"No feature record found for ts={ts}. "
            f"Run --list-unlabelled to see available cycle timestamps."
        )

    rec = OutcomeRecord(
        ts=ts,
        label=label,
        outcome=outcome,
        notes=notes,
        labelled_at=time.time(),
        weight=float(weight),
    )
    labels = _load_labels()
    labels[ts] = rec
    _save_labels(labels)
    log.info(
        "label written ts=%.0f label=%s outcome=%s weight=%.1f",
        ts,
        label,
        outcome,
        weight,
    )
    return rec


def get_label(ts: float) -> Optional[OutcomeRecord]:
    """Return the OutcomeRecord for ts, or None if not yet labelled."""
    return _load_labels().get(ts)


def list_unlabelled(limit: int = 20) -> List[dict]:
    """
    Return up to `limit` feature records that have not yet been labelled.

    Results are ordered most-recent first so the operator can label
    from the latest cycles backward.
    """
    labelled_ts = set(_load_labels().keys())
    features = _load_features()
    unlabelled = [f for f in features if float(f.get("ts", -1)) not in labelled_ts]
    # Most recent first
    unlabelled.sort(key=lambda f: float(f.get("ts", 0)), reverse=True)
    return unlabelled[:limit]


def label_stats() -> Dict[str, object]:
    """
    Return a summary of labelling coverage and class distribution.

    Fields:
        total_features     int — total feature records on disk
        total_labelled     int — how many have been labelled
        coverage_pct       float — labelled / total * 100
        label_counts       dict — count per label class
        outcome_counts     dict — count per outcome class
        ready_to_train     bool — True when >= 200 labelled cycles exist
                                  (minimum for a reliable XGBoost fit)
    """
    features = _load_features()
    labels = _load_labels()

    label_counts: Dict[str, int] = {lbl: 0 for lbl in sorted(VALID_LABELS)}
    outcome_counts: Dict[str, int] = {out: 0 for out in sorted(VALID_OUTCOMES)}
    for rec in labels.values():
        label_counts[rec.label] = label_counts.get(rec.label, 0) + 1
        outcome_counts[rec.outcome] = outcome_counts.get(rec.outcome, 0) + 1

    total_features = len(features)
    total_labelled = len(labels)
    coverage_pct = (
        round(total_labelled / total_features * 100, 1) if total_features > 0 else 0.0
    )

    return {
        "total_features": total_features,
        "total_labelled": total_labelled,
        "coverage_pct": coverage_pct,
        "label_counts": label_counts,
        "outcome_counts": outcome_counts,
        "ready_to_train": total_labelled >= 200,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_feature_row(f: dict) -> None:
    ts = float(f.get("ts", 0))
    phase = f.get("dominant_phase", 0.0)
    events = f.get("convergence_event_count", 0)
    strong = f.get("strong_events", 0)
    # Summarise scar pressures for any domain present
    scar_parts = []
    for k, v in sorted(f.items()):
        if k.endswith("_max_pressure") and k.startswith("scar_") and v > 0:
            domain = k[len("scar_") : -len("_max_pressure")]
            scar_parts.append(f"{domain}={v:.2f}")
    scar_str = "  scars[" + " ".join(scar_parts) + "]" if scar_parts else ""
    print(
        f"  ts={ts:.0f}  {_fmt_ts(ts)}"
        f"  events={events} strong={strong}"
        f"  phase={phase:.3f}{scar_str}"
    )
    print(
        f"    → python -m signal_core.core.ml.outcome_log"
        f" --ts {ts} --label NOISE|COUPLING|LAG --outcome ACTED|HELD|MONITORED"
    )


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="SignalLogic ML — operator label tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Label a cycle
  python -m signal_core.core.ml.outcome_log \\
      --ts 1741000000 --label COUPLING --outcome ACTED

  # High-confidence label (weight 2.0 = more influence in training)
  python -m signal_core.core.ml.outcome_log \\
      --ts 1741000000 --label NOISE --outcome HELD --weight 2.0 \\
      --notes "residual scar pressure from prior day event"

  # Show unlabelled cycles
  python -m signal_core.core.ml.outcome_log --list-unlabelled --limit 10

  # Show training readiness
  python -m signal_core.core.ml.outcome_log --stats
""",
    )
    ap.add_argument(
        "--ts", type=float, help="Cycle timestamp to label (from features.jsonl)"
    )
    ap.add_argument("--label", choices=sorted(VALID_LABELS), help="Ground-truth label")
    ap.add_argument(
        "--outcome", choices=sorted(VALID_OUTCOMES), help="Operator action taken"
    )
    ap.add_argument("--notes", default="", help="Optional free-text notes")
    ap.add_argument(
        "--weight", type=float, default=1.0, help="Training weight (default 1.0)"
    )
    ap.add_argument(
        "--list-unlabelled", action="store_true", help="List unlabelled cycles"
    )
    ap.add_argument("--limit", type=int, default=20, help="Limit for --list-unlabelled")
    ap.add_argument(
        "--stats", action="store_true", help="Show label stats and training readiness"
    )
    args = ap.parse_args()

    if args.stats:
        s = label_stats()
        print(
            f"\nLabel coverage: {s['total_labelled']}/{s['total_features']} ({s['coverage_pct']}%)"
        )
        needed = 200 - s["total_labelled"]
        train_status = (
            "YES — run train.py"
            if s["ready_to_train"]
            else f"NO — need {needed} more labels"
        )
        print(f"Ready to train: {train_status}")
        print("\nLabel distribution:")
        for lbl, count in sorted(s["label_counts"].items()):
            bar = "█" * count
            print(f"  {lbl:<10} {count:>4}  {bar}")
        print("\nOutcome distribution:")
        for out, count in sorted(s["outcome_counts"].items()):
            bar = "█" * count
            print(f"  {out:<12} {count:>4}  {bar}")
        return

    if args.list_unlabelled:
        unlabelled = list_unlabelled(limit=args.limit)
        if not unlabelled:
            print("All cycles labelled.")
            return
        print(f"\nUnlabelled cycles ({len(unlabelled)} shown, most recent first):\n")
        for f in unlabelled:
            _print_feature_row(f)
            print()
        return

    # Label a cycle
    if not args.ts or not args.label or not args.outcome:
        ap.error("--ts, --label, and --outcome are required to write a label")

    try:
        rec = write_label(
            ts=args.ts,
            label=args.label,
            outcome=args.outcome,
            notes=args.notes,
            weight=args.weight,
        )
        print(
            f"Labelled: ts={rec.ts:.0f} ({_fmt_ts(rec.ts)})  "
            f"label={rec.label}  outcome={rec.outcome}  weight={rec.weight}"
        )
    except ValueError as e:
        print(f"Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
