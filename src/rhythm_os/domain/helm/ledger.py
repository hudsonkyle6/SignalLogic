"""
Helm trust ledger — append-only JSONL record of helm recommendations.

Every cycle appends one HelmRecord.  This is the raw material for
retrospective trust scoring: was WAIT followed by adverse conditions?
Was PUSH followed by favorable outcomes?  The ledger accumulates silently
and never blocks the cycle.

Usage
-----
    from rhythm_os.domain.helm.ledger import (
        HelmRecord,
        record_from_helm_result,
        append_helm_record,
        load_helm_records,
    )

    result = compute_helm(cycle_result)
    rec    = record_from_helm_result(result, cycle_ts=cycle_result.cycle_ts)
    append_helm_record(rec)

    recent = load_helm_records(n=5)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List

from rhythm_os.domain.helm.engine import HelmResult
from rhythm_os.runtime.paths import HELM_LOG_PATH


@dataclass
class HelmRecord:
    """One persisted helm recommendation from a cycle."""

    state:          str    # WAIT | PREPARE | ACT | PUSH
    rationale:      str
    ts:             float  # wall-clock time of recommendation (from HelmResult)
    cycle_ts:       float  # CycleResult.cycle_ts

    # Driving metrics — stored for future retrospective scoring
    admission_rate: float = 0.0
    anomaly_rate:   float = 0.0
    strong_events:  int   = 0
    event_count:    int   = 0
    brittleness:    float = 0.0
    strain:         float = 0.0


def record_from_helm_result(result: HelmResult, *, cycle_ts: float) -> HelmRecord:
    """Build a HelmRecord from a HelmResult and the cycle's own timestamp."""
    return HelmRecord(
        state=result.state,
        rationale=result.rationale,
        ts=result.ts,
        cycle_ts=cycle_ts,
        admission_rate=result.admission_rate,
        anomaly_rate=result.anomaly_rate,
        strong_events=result.strong_events,
        event_count=result.event_count,
        brittleness=result.brittleness,
        strain=result.strain,
    )


def append_helm_record(record: HelmRecord) -> None:
    """Append one HelmRecord to the trust ledger (JSONL, append-only)."""
    HELM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HELM_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record)) + "\n")


def load_helm_records(n: int = 20) -> List[HelmRecord]:
    """
    Return the most recent *n* HelmRecord entries from the ledger.

    Returns an empty list when the ledger does not exist or is unreadable.
    Malformed lines are silently skipped.
    """
    if not HELM_LOG_PATH.exists():
        return []
    records: List[HelmRecord] = []
    try:
        with HELM_LOG_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(HelmRecord(**json.loads(line)))
                except Exception:
                    continue
    except OSError:
        return []
    return records[-n:]
