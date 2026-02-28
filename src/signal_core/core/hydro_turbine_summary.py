"""
TURBINE SUMMARY — Post-cycle convergence report

Reads today's turbine basin observations and produces a structured
convergence report for each cycle run.

This closes the Turbine output loop: after Hydro commits, this module
reads what the Turbine observed and surfaces any cross-domain convergence
events as a human-readable, machine-parseable daily summary.

Authority:
  - READ-ONLY from turbine basin
  - NO writes to penstock or dark field
  - NO dispatch authority
  - Appends daily summary to turbine/summary.jsonl only
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Any

from rhythm_os.runtime.paths import TURBINE_DIR
from signal_core.core.log import get_logger

log = get_logger(__name__)
CONVERGENCE_WINDOW = 0.083  # must match hydro_turbine.py


# ------------------------------------------------------------
# Loader
# ------------------------------------------------------------

def _load_today_turbine() -> List[dict]:
    today = datetime.now(timezone.utc).date().isoformat()
    path = TURBINE_DIR / f"{today}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


# ------------------------------------------------------------
# Phase bucketing
# ------------------------------------------------------------

def _phase_bucket(phase: float, buckets: int = 12) -> int:
    """Quantise diurnal phase [0,1] into N equal buckets (default 12 = 2h each)."""
    return int(phase * buckets) % buckets


def _circular_distance(a: float, b: float) -> float:
    d = abs(a - b)
    return min(d, 1.0 - d)


# ------------------------------------------------------------
# Convergence event detection
# ------------------------------------------------------------

def _find_convergence_events(records: List[dict]) -> List[Dict[str, Any]]:
    """
    Scan turbine records for moments where observations from different
    domains cluster at the same diurnal phase window.

    Returns a list of convergence events, each describing which domains
    converged and at what phase.
    """
    if not records:
        return []

    # Sort by diurnal_phase
    sorted_recs = sorted(records, key=lambda r: float(r.get("diurnal_phase", 0)))

    events: List[Dict[str, Any]] = []
    used = set()

    for i, anchor_rec in enumerate(sorted_recs):
        if i in used:
            continue
        anchor_phase = float(anchor_rec.get("diurnal_phase", 0))
        anchor_domain = anchor_rec.get("domain", "?")

        cluster_domains: Dict[str, float] = {anchor_domain: anchor_phase}

        for j, cmp_rec in enumerate(sorted_recs):
            if j == i or j in used:
                continue
            cmp_domain = cmp_rec.get("domain", "?")
            if cmp_domain == anchor_domain:
                continue
            cmp_phase = float(cmp_rec.get("diurnal_phase", 0))
            if _circular_distance(anchor_phase, cmp_phase) <= CONVERGENCE_WINDOW:
                cluster_domains[cmp_domain] = cmp_phase

        if len(cluster_domains) >= 2:
            for idx in [i] + [
                j for j, r in enumerate(sorted_recs)
                if r.get("domain") in cluster_domains and j != i
            ]:
                used.add(idx)

            events.append({
                "diurnal_phase": round(anchor_phase, 4),
                "domains": sorted(cluster_domains.keys()),
                "domain_count": len(cluster_domains),
                "strength": "strong" if len(cluster_domains) >= 3 else "weak",
            })

    return events


# ------------------------------------------------------------
# Summary builder
# ------------------------------------------------------------

def build_summary(records: List[dict]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)

    domain_counts: Dict[str, int] = defaultdict(int)
    for r in records:
        domain_counts[r.get("domain", "unknown")] += 1

    events = _find_convergence_events(records)

    return {
        "ts": now.isoformat(),
        "date": now.date().isoformat(),
        "total_turbine_observations": len(records),
        "domains_observed": dict(domain_counts),
        "convergence_events": events,
        "convergence_event_count": len(events),
        "strong_events": sum(1 for e in events if e["strength"] == "strong"),
    }


def _append_summary(summary: Dict[str, Any]) -> None:
    TURBINE_DIR.mkdir(parents=True, exist_ok=True)
    path = TURBINE_DIR / "summary.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")


# ------------------------------------------------------------
# Print report
# ------------------------------------------------------------

def _log_report(summary: Dict[str, Any]) -> None:
    log.info(
        "turbine summary date=%s observations=%d events=%d strong=%d domains=%s",
        summary["date"],
        summary["total_turbine_observations"],
        summary["convergence_event_count"],
        summary["strong_events"],
        ",".join(sorted(summary["domains_observed"].keys())) or "none",
    )
    for ev in summary.get("convergence_events", []):
        log.info(
            "convergence strength=%s phase=%.3f domains=%s",
            ev["strength"],
            ev["diurnal_phase"],
            ",".join(ev["domains"]),
        )


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def run_turbine_summary() -> Dict[str, Any]:
    """
    Read today's turbine observations, build convergence summary,
    append to summary.jsonl, and print report.

    Returns the summary dict for inspection.
    """
    records = _load_today_turbine()
    summary = build_summary(records)
    _append_summary(summary)
    _log_report(summary)
    return summary


if __name__ == "__main__":
    run_turbine_summary()
