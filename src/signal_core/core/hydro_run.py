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

from signal_core.core.run_cycle_once import run_cycle_once
from signal_core.core.hydro_run_daily import main as _hydro_daily, CycleResult


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

    return result


def main() -> None:
    result = run_full_cycle()
    bs = result.baseline_status

    print(f"\nFULL CYCLE COMPLETE")
    print(f"  drained:     {result.packets_drained}")
    print(f"  rejected:    {result.rejected}")
    print(f"  committed:   {result.committed}")
    print(f"  turbine:     {result.turbine_obs}")
    print(f"  quarantined: {result.spillway_quarantined}")
    print(f"  hold:        {result.spillway_hold}")
    if result.convergence_summary:
        ev = result.convergence_summary.get("convergence_event_count", 0)
        strong = result.convergence_summary.get("strong_events", 0)
        print(f"  convergence: {ev} events ({strong} strong)")
    if bs:
        print(f"\nBASELINE:  {bs.summary()}")


if __name__ == "__main__":
    main()
