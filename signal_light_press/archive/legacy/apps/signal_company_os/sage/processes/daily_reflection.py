"""
daily_cycle.py

SageOS — Daily Cycle
Runs the HST rhythm engine, updates state memory, and prints the Morning Field Brief.

Usage:
    python -m processes.daily_cycle
"""

from __future__ import annotations
import sys
import json
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------
# Ensure SageOS root is on sys.path
# ------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------------------------------------------------------
# Imports from SageOS core
# ------------------------------------------------------
from registry_loader import load_registry, resolve_path
from rhythms.sage_hst import run_daily_sage_hst


# ------------------------------------------------------
# Internal helpers
# ------------------------------------------------------
def _print_header(reg: dict) -> None:
    root = reg["paths"]["root"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("══════════════════════════════════════")
    print("          🌿 SAGEOS — DAILY CYCLE")
    print("══════════════════════════════════════")
    print(f" Root:    {root}")
    print(f" Time:    {now}")
    print("──────────────────────────────────────")


def _update_sage_state(reg: dict, summary: dict) -> None:
    """
    Write updated daily cycle information to SageOS state memory.
    """
    state_path = resolve_path(reg, "state", "sage_state")
    state_path.parent.mkdir(parents=True, exist_ok=True)

    if state_path.exists():
        try:
            with state_path.open("r", encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}

    state["last_daily_cycle"] = summary.get("date_iso")
    state["human_phase"] = summary.get("human_phase", "baseline")
    state["household_phase"] = summary.get("household_phase", "baseline")
    state["seasonal_phase"] = summary.get("seasonal_phase", "Reflect")

    state["version"] = reg["version"]["sageOS"]
    state["schema"] = reg["version"]["spec"]

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _print_morning_brief(summary: dict) -> None:
    """
    Render the Morning Field Brief.
    """

    print("        📜 MORNING FIELD BRIEF")
    print("──────────────────────────────────────")

    print(f" Date:              {summary['date_iso']}")
    print(f" Season / Inner:    {summary['season']} / {summary['inner_season']}")
    print()

    print(" Human & Household")
    print(" -----------------")
    print(f"  Human energy:     {summary['human_energy']}")
    print(f"  Household energy: {summary['household_energy']}")
    print(f"  Seasonal energy:  {summary['seasonal_energy']}")
    print()

    print(" Oracle Field")
    print(" ------------")
    print(f"  Oracle Resonance: {summary['oracle_resonance']}")
    print(f"  Oracle Amplitude: {summary['oracle_amplitude']}")
    print(f"  Oracle H_t:       {summary['oracle_ht']}")
    print()

    print(" Harmony & Drift")
    print(" ---------------")
    print(f"  HST alignment:    {summary['hst_alignment']}")
    print(f"  Harmony score:    {summary['harmony_score']}")
    print(f"  Drift index:      {summary['drift_index']}")
    print()

    print(" Readiness")
    print(" ---------")
    print(f"  Readiness level:  {summary['readiness_level']}")
    print(f"  Guidance:         {summary['guidance']}")
    print("──────────────────────────────────────")


# ------------------------------------------------------
# Main entry point
# ------------------------------------------------------
def main() -> None:
    reg = load_registry()
    _print_header(reg)

    summary = run_daily_sage_hst(reg)

    _update_sage_state(reg, summary)

    _print_morning_brief(summary)

    print("══════════════════════════════════════")
    print(" SageOS daily cycle complete.")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    main()

