"""
Canonical Cycle Runner — Single Step (Thin)

Purpose:
- Execute one deterministic Rhythm OS cycle step
- Emit reserve + antifragile descriptors
- Emit alignment summaries
- No scheduling, no looping, no authority

Invocation:
    python bin/run_cycle_once.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------
# Path discipline: ensure repo root is on PYTHONPATH
# ---------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------
# Imports (runtime-only, no planners, no gates)
# ---------------------------------------------------------------------

from rhythm_os.runtime.reserve import emit_drift_index
from rhythm_os.runtime.antifragile.state_emit import emit_antifragile_state
from rhythm_os.runtime.alignment import emit_convergence_summary

# ---------------------------------------------------------------------
# Configuration (explicit, static)
# ---------------------------------------------------------------------

BUS_DIR = Path("rhythm_os/data/dark_field")
HISTORY_WINDOW_SEC = 24.0 * 3600.0

# Drift / Antifragile source
SOURCE_DOMAIN = "core"
SOURCE_CHANNEL = "bootstrap_calibration"

DRIFT_BASELINE_N = 12
STRAIN_WINDOW_N = 12

# Alignment configuration
ALIGN_WITHIN_DEG = 30.0

# ---------------------------------------------------------------------
# Cycle Runner
# ---------------------------------------------------------------------

def run_cycle_once() -> None:
    """
    Execute a single canonical Rhythm OS cycle.

    Phases:
      Phase 3   — Reserve (drift_index)
      Phase 3.5 — Antifragile (unknowns, strain, brittleness)
      Phase 4   — Alignment (oracle geometry)
    """

    # Deterministic cycle anchor (seconds resolution)
    t_ref = float(int(time.time()))

    # --------------------------------------------------
    # Phase 3 — Reserve (DRIFT only)
    # --------------------------------------------------

    emit_drift_index(
        bus_dir=BUS_DIR,
        t_ref=t_ref,
        history_window_sec=HISTORY_WINDOW_SEC,
        source_domain=SOURCE_DOMAIN,
        source_channel=SOURCE_CHANNEL,
        baseline_n=DRIFT_BASELINE_N,
    )

    # --------------------------------------------------
    # Phase 3.5 — Antifragile Runtime (DESCRIPTORS ONLY)
    # --------------------------------------------------

    emit_antifragile_state(
        bus_dir=BUS_DIR,
        t_ref=t_ref,
        history_window_sec=HISTORY_WINDOW_SEC,
        source_domain=SOURCE_DOMAIN,
        source_channel=SOURCE_CHANNEL,
        baseline_n=DRIFT_BASELINE_N,
        strain_window_n=STRAIN_WINDOW_N,
        rest_factor="none",
        emit_drift_if_missing=False,   # drift handled upstream
        cycle_id=f"cycle@{int(t_ref)}",
        version="v1",
    )

    # --------------------------------------------------
    # Phase 4 — Alignment (Oracle geometry)
    # --------------------------------------------------

    emit_convergence_summary(
        bus_dir=BUS_DIR,
        t_ref=t_ref,
        history_window_sec=HISTORY_WINDOW_SEC,
        within_deg=ALIGN_WITHIN_DEG,
    )


# ---------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    run_cycle_once()

