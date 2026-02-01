"""
init_state.py

Initialize or reset SageOS state file (state/sage_state.json).

Run:
    python -m processes.init_state
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from registry_loader import load_registry, resolve_path  # type: ignore


def main() -> None:
    reg = load_registry()
    state_path = resolve_path(reg, "state", "sage_state")
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "last_daily_cycle": None,
        "last_weekly_cycle": None,
        "last_seasonal_cycle": None,
        "human_phase": "baseline",
        "household_phase": "baseline",
        "seasonal_phase": "Reflect",
        "version": reg["version"]["sageOS"],
        "schema": reg["version"]["spec"],
    }

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"SageOS state initialized at: {state_path}")


if __name__ == "__main__":
    main()
