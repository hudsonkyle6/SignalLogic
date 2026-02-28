#!/usr/bin/env python3
"""
Signal Hydro — Full Cycle Orchestrator
POSTURE: OBSERVATORY (sequences hydro components)

This is the single entry point for a complete observation + commit cycle.

Sequence:
  1. observe_once()       → produce one HydroPacket from current sensor state
  2. gate + enqueue       → structurally admit to ingress queue
  3. drain + commit       → hydro daily cadence (gate, dispatch, commit, turbine)
  4. return CycleResult   → structured summary for caller / scheduler

Usage:
    python -m signal_core.core.hydro_run          # one full cycle
    # or call run_full_cycle() from a scheduler

Deployment note:
    The observer in run_cycle_once.py is a bootstrap stub.
    Replace observe_once() with a real sensor adapter before deployment.
    The orchestrator itself does not need to change.
"""

from __future__ import annotations

from signal_core.core.run_cycle_once import run_cycle_once
from signal_core.core.hydro_run_daily import main as _hydro_daily, CycleResult


def run_full_cycle() -> CycleResult:
    """
    Execute one complete hydro cycle end-to-end.

    Steps:
      1. Observe current state → enqueue one packet
      2. Drain queue → gate → dispatch → commit → turbine summary

    Returns:
        CycleResult with structured counts and convergence summary.
    """
    # Step 1: observe and enqueue
    run_cycle_once()

    # Step 2: drain, commit, summarize
    return _hydro_daily()


if __name__ == "__main__":
    result = run_full_cycle()
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
