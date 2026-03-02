#!/usr/bin/env python3
"""
SignalLogic — One Full Observation Cycle

Phase 1 Regime:
    - System pressure primary (real vitals, 75-second window)
    - Cyber cadence projection
    - Natural live (Open-Meteo)
    - Market muted

Sequence:
    1. System meter window  — accumulate real vitals
    2. Natural observation  — weather / pressure / thermal
    3. Cyber projection     — cadence domain
    4. System domain        — PSR transform + ingress
    5. Hydro                — gate / dispatch / commit / turbine
    6. Helix dashboard      — cycle summary snapshot
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


# ─── UTF-8 transport ──────────────────────────────────────────────────────────

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── Paths and environment ────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]
PY   = sys.executable

BASE_ENV = os.environ.copy()
BASE_ENV["PYTHONUTF8"]       = "1"
BASE_ENV["PYTHONIOENCODING"] = "utf-8"

_existing = BASE_ENV.get("PYTHONPATH", "")
BASE_ENV["PYTHONPATH"] = os.pathsep.join(
    p for p in [str(ROOT / "src"), str(ROOT), _existing] if p
)

# ─── Cycle configuration ──────────────────────────────────────────────────────

SYSTEM_OBS_WINDOW_S = 75

ENABLE_NATURAL = True
ENABLE_MARKET  = False
ENABLE_CYBER   = True


# ─── Helpers ──────────────────────────────────────────────────────────────────

def run_module(label: str, module_path: str, required: bool = True) -> bool:
    print("\n" + "=" * 72)
    print(label)
    print("CMD:", f"{PY} -m {module_path}")
    print("=" * 72)

    p = subprocess.run(
        [PY, "-m", module_path],
        cwd=str(ROOT),
        env=BASE_ENV,
    )

    if p.returncode != 0:
        if required:
            sys.exit(f"FAILED: {label}")
        print(f"{label}: skipped (non-critical)")
        return False

    return True


def countdown(seconds: int, label: str) -> None:
    for remaining in range(seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r{label}: {mins:02d}:{secs:02d} remaining", end="", flush=True)
        time.sleep(1)
    print(f"\r{label}: DONE{' ' * 24}")


def _helix_live(seconds: int, label: str, stop_event=None) -> None:
    """
    Show the rotating helix for `seconds` seconds with a countdown banner.
    Falls back to plain text countdown if rich/dashboard is unavailable.
    Exits early if `stop_event` is set (used during loop inter-cycle wait).
    """
    try:
        from signal_core.core.dashboard.helix_dashboard import (
            _build_display, _load_last_cycle_result, _HAS_RICH,
        )
    except Exception:
        countdown(seconds, label)
        return

    if not _HAS_RICH:
        countdown(seconds, label)
        return

    from rich.console import Console
    from rich.live import Live

    console = Console()
    rotation = 0.0
    fps = 8.0
    frame_s = 1.0 / fps
    end = time.monotonic() + seconds
    cycle_result = _load_last_cycle_result()

    with Live(console=console, refresh_per_second=fps, screen=True) as live:
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            if stop_event is not None and stop_event.is_set():
                break
            mins, secs_left = divmod(int(remaining), 60)
            status = f"{label}  —  {mins:02d}:{secs_left:02d} remaining"
            live.update(_build_display(rotation=rotation, cycle_result=cycle_result, status_text=status))
            time.sleep(frame_s)
            rotation += 0.08


# ─── Main cycle ───────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 72)
    print("=== BEGIN SIGNAL CYCLE ===")
    print("=" * 72)

    # ── 1. System meter window ────────────────────────────────────────────────

    print("\n--- SYSTEM OBSERVATION WINDOW ---")

    meter_proc = subprocess.Popen(
        [PY, "src/signal_core/core/instruments/hydro_meter.py"],
        cwd=str(ROOT),
        env=BASE_ENV,
    )

    try:
        _helix_live(SYSTEM_OBS_WINDOW_S, "SYSTEM METER WINDOW")
    finally:
        meter_proc.terminate()
        meter_proc.wait(timeout=10)

    print("--- SYSTEM OBSERVATION WINDOW CLOSED ---")

    # ── 2. Natural observation ────────────────────────────────────────────────

    if ENABLE_NATURAL:
        natural_ok = run_module(
            "OBSERVATORY → NATURAL RAW",
            "apps.observatory_tools.emit_natural_raw_once",
            required=False,
        )
        if natural_ok:
            run_module("PSR → NATURAL DOMAIN",  "apps.psr_tools.emit_natural_domain",        required=False)
            run_module("INGRESS → NATURAL",      "apps.psr_tools.domain_to_natural_ingress",  required=False)
    else:
        print("\nNATURAL: muted")

    # ── 3. Market (muted) ─────────────────────────────────────────────────────

    if ENABLE_MARKET:
        market_ok = run_module(
            "OBSERVATORY → MARKET RAW",
            "apps.observatory_tools.emit_market_raw_once",
            required=False,
        )
        if market_ok:
            domain_ok = run_module("PSR → MARKET DOMAIN", "apps.psr_tools.observe_market_daily",      required=False)
            if domain_ok:
                run_module("INGRESS → MARKET",             "apps.psr_tools.domain_to_market_ingress", required=False)
    else:
        print("\nMARKET: muted")

    # ── 4. Cyber projection ───────────────────────────────────────────────────

    if ENABLE_CYBER:
        run_module("PSR → CYBER DOMAIN", "apps.psr_tools.emit_cyber_domain",      required=False)
        run_module("INGRESS → CYBER",    "apps.psr_tools.domain_to_cyber_ingress", required=False)
    else:
        print("\nCYBER: muted")

    # ── 5. System domain + ingress ────────────────────────────────────────────

    run_module("PSR → SYSTEM DOMAIN", "apps.psr_tools.emit_system_domain",      required=True)
    run_module("INGRESS → SYSTEM",    "apps.psr_tools.domain_to_system_ingress", required=True)

    # ── 6. Hydro: gate / dispatch / commit / turbine ──────────────────────────

    run_module(
        "HYDRO → GATE / DISPATCH / COMMIT",
        "src.signal_core.core.hydro_run_cadence",
        required=True,
    )

    # ── 7. Helix dashboard snapshot ───────────────────────────────────────────

    run_module(
        "HELIX → CYCLE SUMMARY",
        "signal_core.core.dashboard.helix_dashboard",
        required=False,
    )

    print("\n" + "=" * 72)
    print("=== END SIGNAL CYCLE ===")
    print("=" * 72)


def _run_loop(interval_s: int) -> None:
    """
    Run full cycles repeatedly, sleeping `interval_s` between completions.
    Exits cleanly on SIGINT / SIGTERM.
    """
    import signal as _signal
    import threading

    stop = threading.Event()
    _signal.signal(_signal.SIGTERM, lambda *_: stop.set())
    _signal.signal(_signal.SIGINT,  lambda *_: stop.set())

    cycle = 0
    while not stop.is_set():
        cycle += 1
        print(f"\n{'#' * 72}")
        print(f"# CYCLE {cycle}  (loop interval={interval_s}s)")
        print(f"{'#' * 72}")
        try:
            main()
        except SystemExit as exc:
            # A required step failed — log and wait before retrying
            print(f"\nCYCLE {cycle} FAILED: {exc} — retrying after {interval_s}s")

        if not stop.is_set():
            _helix_live(interval_s, "Next cycle in", stop_event=stop)

    print("\nSignalLogic loop stopped.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="SignalLogic — full observation cycle")
    ap.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECONDS",
        help="run cycles repeatedly, sleeping SECONDS between completions (0 = run once)",
    )
    args = ap.parse_args()

    if args.loop > 0:
        _run_loop(args.loop)
    else:
        main()
