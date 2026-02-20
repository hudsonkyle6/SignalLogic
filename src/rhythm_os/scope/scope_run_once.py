#!/usr/bin/env python3
"""
SIGNAL SCOPE — ONE-SHOT OBSERVATION

POSTURE:
- READ-ONLY
- NO AUTHORITY
- NO STATE
- NO TIME OWNERSHIP

Renders sealed Waves already committed to the Dark Field penstock.
"""

from __future__ import annotations

from pathlib import Path

from rhythm_os.scope.signal_scope import render_scope
from rhythm_os.scope.adapters.dark_field_loader import load_penstock


# ---------------------------------------------------------------------
# Paths (aligned with Hydro)
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # SignalLogic/
PENSTOCK_DIR = PROJECT_ROOT / "src" / "rhythm_os" / "data" / "dark_field" / "penstock"

print("FILES FOUND:", list(PENSTOCK_DIR.glob("*.jsonl")))

# ---------------------------------------------------------------------
# Load Waves (read-only)
# ---------------------------------------------------------------------

def load_waves():
    """
    Load sealed Waves from the penstock.
    Silent if none exist.
    """
    if not PENSTOCK_DIR.exists():
        return []

    return list(load_penstock(PENSTOCK_DIR))


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    print("SCOPE PENSTOCK DIR:", PENSTOCK_DIR.resolve())
    waves = load_waves()
    print("WAVES LOADED:", len(waves))

    render_scope(
        waves,
        window=120,
    )



if __name__ == "__main__":
    main()
