#!/usr/bin/env python3
"""
Signal Hydro — Full Cycle Orchestrator
POSTURE: OBSERVATORY (sequences hydro components)

This is the single entry point for a complete observation + commit cycle.

Sequence:
  1. check_readiness()   → assess baseline warmth for each signature tier
  2. observe_once()      → produce one HydroPacket from current system state
  3. gate + enqueue      → structurally admit to ingress queue
  4. drain + commit      → hydro daily cadence (gate, dispatch, commit, turbine)
  5. return CycleResult  → structured summary with readiness status attached

Usage:
    python -m signal_core.core.hydro_run          # one full cycle
    # or call run_full_cycle() from a scheduler
"""

from __future__ import annotations

import dataclasses
import sys

from signal_core.core.log import configure, get_logger
from signal_core.core.run_cycle_once import run_cycle_once
from signal_core.core.hydro_run_cadence import main as _hydro_daily, CycleResult

configure()
log = get_logger(__name__)


def run_full_cycle() -> CycleResult:
    """
    Execute one complete hydro cycle end-to-end.

    Steps:
      1. Check signature-tier readiness (system + natural baselines)
      2. Observe current system state → enqueue one packet
      3. Drain queue → gate → dispatch → commit → turbine summary
      4. Attach ReadinessStatus to CycleResult

    The system always runs regardless of readiness — the status is
    informational, surfaced in the dashboard and logs.

    Returns:
        CycleResult with structured counts, convergence summary,
        and baseline_status for all signature tiers.
    """
    # Step 1: assess baseline warmth
    from rhythm_os.runtime.readiness import check_readiness
    from rhythm_os.runtime.deploy_config import get_baseline_requirements

    readiness = check_readiness(**get_baseline_requirements())

    # Step 2: observe and enqueue
    run_cycle_once()

    # Step 3: drain, commit, summarize
    result = _hydro_daily()

    # Step 4: attach readiness to result
    result = dataclasses.replace(result, baseline_status=readiness)

    # Step 5: extract ML feature vector and append to data/ml/features.jsonl
    try:
        from signal_core.core.ml.feature_builder import extract_and_append

        extract_and_append(result)
    except Exception:
        log.warning("ml feature extraction failed — cycle result unaffected", exc_info=True)

    return result


def _health_check() -> int:
    """Return 0 if system is warm/ready, 1 if cold/degraded, 2 on error."""
    try:
        from rhythm_os.runtime.readiness import check_readiness
        from rhythm_os.runtime.deploy_config import get_baseline_requirements

        status = check_readiness(**get_baseline_requirements())
        return 0 if status.overall_ready else 1
    except Exception:
        log.exception("health check failed")
        return 2


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="SignalLogic — full observation cycle")
    ap.add_argument(
        "--health",
        action="store_true",
        help="check system readiness and exit 0 (warm), 1 (cold), 2 (error)",
    )
    ap.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECONDS",
        help="run cycles on a schedule every N seconds; 0 = run once and exit",
    )
    args = ap.parse_args()

    if args.health:
        sys.exit(_health_check())

    import signal as _signal
    import threading

    _stop = threading.Event()
    _signal.signal(_signal.SIGTERM, lambda *_: _stop.set())
    _signal.signal(_signal.SIGINT, lambda *_: _stop.set())

    def _run_once() -> None:
        result = run_full_cycle()
        bs = result.baseline_status
        log.info(
            "cycle complete",
            extra={} if True else None,
        )
        log.info(
            "full cycle complete — drained=%d rejected=%d committed=%d "
            "turbine=%d quarantined=%d hold=%d",
            result.packets_drained,
            result.rejected,
            result.committed,
            result.turbine_obs,
            result.spillway_quarantined,
            result.spillway_hold,
        )
        if result.convergence_summary:
            ev = result.convergence_summary.get("convergence_event_count", 0)
            strong = result.convergence_summary.get("strong_events", 0)
            log.info("convergence events=%d strong=%d", ev, strong)
        if bs:
            log.info("baseline %s", bs.summary())

    if args.loop > 0:
        log.info("signallogic starting loop interval=%ds", args.loop)
        while not _stop.is_set():
            try:
                _run_once()
            except Exception:
                log.exception("cycle failed")
            _stop.wait(timeout=args.loop)
        log.info("signallogic stopped")
    else:
        _run_once()


if __name__ == "__main__":
    main()
