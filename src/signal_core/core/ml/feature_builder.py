"""
ML Feature Builder — per-cycle feature vector extraction.
POSTURE: OBSERVATORY (read-only from all live stores)

Appends one flat JSON record per cycle to data/ml/features.jsonl.

Each record contains:
  - Temporal context (diurnal phase, hour, day, month)
  - Turbine convergence summary (event counts, strength, dominant phase)
  - Per-domain scar aggregate state (pressure, reinforcement, trigger mix)
  - Readiness tier status (system + natural warmth)
  - Cycle-level packet statistics

No ML inference happens here — purely feature extraction and persistence.
These records become the training dataset for the XGBoost classifier and,
eventually, the Temporal Fusion Transformer once 30+ days have accumulated.

Authority:
  - READ-ONLY from all live stores (scars, turbine, readiness)
  - WRITE to data/ml/features.jsonl only
  - No dispatch, gate, or routing authority
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from rhythm_os.runtime.paths import ML_DIR, SCARS_DIR
from signal_core.core.log import get_logger

log = get_logger(__name__)

_FEATURES_PATH = ML_DIR / "features.jsonl"


# ---------------------------------------------------------------------------
# Scar feature extraction
# ---------------------------------------------------------------------------


def _scar_features_for_domain(domain: str) -> Dict[str, Any]:
    """
    Read all active scars for a domain directly from its JSONL file and
    compute aggregate features.

    Returns zero-valued features if the domain has no scar file.
    Prefixed with "scar_{domain}_" so all domains coexist in a flat dict.
    """
    path = SCARS_DIR / f"{domain}.jsonl"
    prefix = f"scar_{domain}"
    zero = {
        f"{prefix}_count": 0,
        f"{prefix}_max_pressure": 0.0,
        f"{prefix}_avg_pressure": 0.0,
        f"{prefix}_ever_changed_count": 0,
        f"{prefix}_compound_count": 0,
        f"{prefix}_avg_reinforcements": 0.0,
    }

    if not path.exists():
        return zero

    scars = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                scars.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return zero

    if not scars:
        return zero

    pressures = [float(s.get("pressure", 0.0)) for s in scars]
    reinforcements = [int(s.get("reinforcement_count", 0)) for s in scars]

    return {
        f"{prefix}_count": len(scars),
        f"{prefix}_max_pressure": round(max(pressures), 4),
        f"{prefix}_avg_pressure": round(sum(pressures) / len(pressures), 4),
        f"{prefix}_ever_changed_count": sum(1 for s in scars if s.get("ever_changed")),
        f"{prefix}_compound_count": sum(
            1 for s in scars if s.get("trigger") == "compound"
        ),
        f"{prefix}_avg_reinforcements": round(
            sum(reinforcements) / len(reinforcements), 2
        ),
    }


def _all_scar_features() -> Dict[str, Any]:
    """
    Enumerate all domain scar files and return aggregate features for each.

    Domains are dynamic — whatever .jsonl files exist in SCARS_DIR are included.
    The feature set grows as new domains are introduced, which XGBoost handles
    gracefully via column alignment at training time.
    """
    features: Dict[str, Any] = {}
    if not SCARS_DIR.exists():
        return features
    for path in sorted(SCARS_DIR.glob("*.jsonl")):
        domain = path.stem
        features.update(_scar_features_for_domain(domain))
    return features


# ---------------------------------------------------------------------------
# Convergence feature extraction
# ---------------------------------------------------------------------------


def _convergence_features(convergence_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Flatten the turbine convergence summary dict into scalar features.

    dominant_phase: the diurnal phase of the event with the most domains
    involved — represents the "centre of gravity" of today's signal.
    """
    if not convergence_summary:
        return {
            "convergence_event_count": 0,
            "strong_events": 0,
            "total_turbine_obs": 0,
            "turbine_domain_count": 0,
            "max_event_domain_count": 0,
            "dominant_phase": 0.0,
            "has_convergence": False,
        }

    events = convergence_summary.get("convergence_events", [])
    domains_observed = convergence_summary.get("domains_observed", {})

    # Phase of the event that involves the most domains
    dominant_phase = 0.0
    max_domain_count = 0
    for ev in events:
        dc = int(ev.get("domain_count", 0))
        if dc > max_domain_count:
            max_domain_count = dc
            dominant_phase = float(ev.get("diurnal_phase", 0.0))

    return {
        "convergence_event_count": int(
            convergence_summary.get("convergence_event_count", 0)
        ),
        "strong_events": int(convergence_summary.get("strong_events", 0)),
        "total_turbine_obs": int(
            convergence_summary.get("total_turbine_observations", 0)
        ),
        "turbine_domain_count": len(domains_observed),
        "max_event_domain_count": max_domain_count,
        "dominant_phase": round(dominant_phase, 4),
        "has_convergence": len(events) > 0,
    }


# ---------------------------------------------------------------------------
# Temporal feature extraction
# ---------------------------------------------------------------------------


def _temporal_features(ts: float) -> Dict[str, Any]:
    """
    Derive temporal context from the cycle timestamp.

    diurnal_phase [0, 1): fraction of the 24-hour day elapsed — matches the
    same coordinate used by the turbine and lighthouse so features are
    directly comparable to convergence event phases.
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    diurnal_phase = (dt.hour * 3600 + dt.minute * 60 + dt.second) / 86400.0
    return {
        "diurnal_phase": round(diurnal_phase, 4),
        "hour_of_day": dt.hour,
        "day_of_week": dt.weekday(),  # 0 = Monday, 6 = Sunday
        "month": dt.month,
    }


# ---------------------------------------------------------------------------
# Readiness feature extraction
# ---------------------------------------------------------------------------


def _readiness_features(baseline_status: Optional[Any]) -> Dict[str, Any]:
    """
    Extract tier warmth from ReadinessStatus.

    Cold tiers mean the classifier is operating with less baseline context —
    an important signal for calibrating confidence in a given cycle.
    """
    if baseline_status is None:
        return {
            "system_ready": False,
            "natural_ready": False,
            "system_count": 0,
            "natural_count": 0,
        }
    return {
        "system_ready": bool(baseline_status.system_ready),
        "natural_ready": bool(baseline_status.natural_ready),
        "system_count": int(baseline_status.system_count),
        "natural_count": int(baseline_status.natural_count),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_features(cycle_result: Any) -> Dict[str, Any]:
    """
    Build a flat, JSON-serialisable feature dict from a completed CycleResult.

    Field categories (all scalars — no nested dicts):
      ts                      unix timestamp of the cycle
      diurnal_phase           [0,1) fraction of 24h day
      hour_of_day             0-23
      day_of_week             0-6 (Monday=0)
      month                   1-12
      convergence_event_count int
      strong_events           int
      total_turbine_obs       int
      turbine_domain_count    int
      max_event_domain_count  int
      dominant_phase          [0,1)
      has_convergence         bool
      system_ready            bool
      natural_ready           bool
      system_count            int
      natural_count           int
      scar_{domain}_*         per-domain scar aggregates (dynamic)
      packets_drained         int
      rejected                int
      committed               int
      turbine_obs             int
      spillway_quarantined    int
      spillway_hold           int

    label (str) is NOT included here — it is appended separately by the
    operator via outcome_log.py when the cycle outcome is known.
    """
    ts = float(getattr(cycle_result, "cycle_ts", time.time()))

    features: Dict[str, Any] = {"ts": ts}
    features.update(_temporal_features(ts))
    features.update(
        _convergence_features(
            getattr(cycle_result, "convergence_summary", None)
        )
    )
    features.update(
        _readiness_features(getattr(cycle_result, "baseline_status", None))
    )
    features.update(_all_scar_features())

    # Cycle-level packet statistics
    for field in (
        "packets_drained",
        "rejected",
        "committed",
        "turbine_obs",
        "spillway_quarantined",
        "spillway_hold",
    ):
        features[field] = int(getattr(cycle_result, field, 0))

    return features


def append_features(features: Dict[str, Any]) -> Path:
    """
    Append one feature dict as a JSON line to data/ml/features.jsonl.

    Creates the file and parent directory on first write.
    Returns the path for logging / testing.
    """
    ML_DIR.mkdir(parents=True, exist_ok=True)
    with _FEATURES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(features, sort_keys=True, separators=(",", ":")) + "\n")
    return _FEATURES_PATH


def extract_and_append(cycle_result: Any) -> Dict[str, Any]:
    """
    Extract features from a completed CycleResult and persist to features.jsonl.

    This is the primary integration point.  Call it at the end of
    run_full_cycle() after all processing is complete.

    Returns the feature dict for inspection and testing.
    """
    features = extract_features(cycle_result)
    path = append_features(features)
    log.debug(
        "ml features appended path=%s ts=%.0f convergence=%d scars=%d",
        path,
        features.get("ts", 0),
        features.get("convergence_event_count", 0),
        sum(1 for k in features if k.endswith("_count") and k.startswith("scar_")),
    )
    return features
