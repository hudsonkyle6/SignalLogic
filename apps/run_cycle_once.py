#!/usr/bin/env python3
"""
SignalLogic — Continuous Observation Runner

The rotating helix is always visible. All subprocess output is suppressed.
A status banner on the helix updates as each step progresses.

Usage:
    python apps/run_cycle_once.py              # one cycle, helix visible throughout
    python apps/run_cycle_once.py --loop 300   # loop every 5 min, helix never stops
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import threading
import signal as _signal
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
ENABLE_MARKET  = True
ENABLE_CYBER   = True


# ─── Exceptions ───────────────────────────────────────────────────────────────

class _CycleFailed(Exception):
    pass


# ─── Silent step runner ───────────────────────────────────────────────────────

def _run_step(module_path: str, required: bool = True) -> bool:
    """Run a Python module as a subprocess. All output suppressed."""
    p = subprocess.run(
        [PY, "-m", module_path],
        cwd=str(ROOT),
        env=BASE_ENV,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if p.returncode != 0:
        if required:
            raise _CycleFailed(module_path)
        return False
    return True


# ─── Cycle steps (runs in background thread) ─────────────────────────────────

def _run_cycle_steps(set_status) -> None:
    """
    Execute the full observation cycle. Calls set_status(text) before each step
    so the helix display can show progress. Raises _CycleFailed on required failure.
    """
    # ── 1. System meter window ────────────────────────────────────────────────
    meter_proc = subprocess.Popen(
        [PY, "src/signal_core/core/instruments/hydro_meter.py"],
        cwd=str(ROOT),
        env=BASE_ENV,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        end = time.monotonic() + SYSTEM_OBS_WINDOW_S
        while time.monotonic() < end:
            remaining = int(end - time.monotonic())
            mins, secs = divmod(remaining, 60)
            set_status(f"SYSTEM METER WINDOW  —  {mins:02d}:{secs:02d} remaining")
            time.sleep(1)
    finally:
        meter_proc.terminate()
        meter_proc.wait(timeout=10)

    # ── 2. Natural observation ─────────────────────────────────────────────────
    if ENABLE_NATURAL:
        set_status("OBSERVATORY → NATURAL RAW")
        natural_ok = _run_step("apps.observatory_tools.emit_natural_raw_once", required=False)
        if natural_ok:
            set_status("PSR → NATURAL DOMAIN")
            _run_step("apps.psr_tools.emit_natural_domain", required=False)
            set_status("INGRESS → NATURAL")
            _run_step("apps.psr_tools.domain_to_natural_ingress", required=False)

    # ── 3. Market ─────────────────────────────────────────────────────────────
    if ENABLE_MARKET:
        set_status("OBSERVATORY → MARKET RAW")
        market_ok = _run_step("apps.observatory_tools.emit_market_raw_once", required=False)
        if market_ok:
            set_status("PSR → MARKET DOMAIN")
            domain_ok = _run_step("apps.psr_tools.observe_market_daily", required=False)
            if domain_ok:
                set_status("INGRESS → MARKET")
                _run_step("apps.psr_tools.domain_to_market_ingress", required=False)

    # ── 4. Cyber projection ───────────────────────────────────────────────────
    if ENABLE_CYBER:
        set_status("PSR → CYBER DOMAIN")
        _run_step("apps.psr_tools.emit_cyber_domain", required=False)
        set_status("INGRESS → CYBER")
        _run_step("apps.psr_tools.domain_to_cyber_ingress", required=False)

    # ── 5. System domain + ingress ────────────────────────────────────────────
    set_status("PSR → SYSTEM DOMAIN")
    _run_step("apps.psr_tools.emit_system_domain", required=True)
    set_status("INGRESS → SYSTEM")
    _run_step("apps.psr_tools.domain_to_system_ingress", required=True)

    # ── 6. Hydro: gate / dispatch / commit / turbine ──────────────────────────
    set_status("HYDRO → GATE / DISPATCH / COMMIT")
    _run_step("src.signal_core.core.hydro_run_cadence", required=True)

    set_status("CYCLE COMPLETE")


# ─── Helix live driver (main entry point) ────────────────────────────────────

def _run_with_helix(interval_s: int = 0) -> None:
    """
    Run observation cycles under the rotating helix display.
    The cycle steps run in a background thread; the helix Live context
    runs in the main thread showing the current step as a status banner.

    interval_s=0  → run one cycle then exit
    interval_s>0  → loop indefinitely, helix stays up between cycles
    """
    try:
        from signal_core.core.dashboard.helix_dashboard import (
            _build_display, _load_last_cycle_result, _HAS_RICH,
        )
    except Exception as exc:
        _run_text_mode(interval_s)
        return

    if not _HAS_RICH:
        _run_text_mode(interval_s)
        return

    from rich.console import Console
    from rich.live import Live

    stop = threading.Event()
    _signal.signal(_signal.SIGTERM, lambda *_: stop.set())
    _signal.signal(_signal.SIGINT,  lambda *_: stop.set())

    status_ref = [""]
    failed_ref = [None]
    cycle_done = threading.Event()

    def set_status(text: str) -> None:
        status_ref[0] = text

    def cycle_worker() -> None:
        try:
            _run_cycle_steps(set_status)
        except _CycleFailed as exc:
            failed_ref[0] = str(exc)
            set_status(f"FAILED: {exc}")
        finally:
            cycle_done.set()

    console = Console()
    fps     = 8.0
    frame_s = 1.0 / fps
    rotation = 0.0
    cycle_num = 0

    with Live(console=console, refresh_per_second=fps, screen=True) as live:
        while not stop.is_set():
            # ── Start cycle in background ─────────────────────────────────────
            cycle_num += 1
            cycle_done.clear()
            failed_ref[0] = None
            set_status(f"CYCLE {cycle_num} — starting…")

            t = threading.Thread(target=cycle_worker, daemon=True)
            t.start()

            # ── Helix drives while cycle runs ─────────────────────────────────
            while not cycle_done.is_set() and not stop.is_set():
                live.update(_build_display(
                    rotation=rotation,
                    cycle_result=_load_last_cycle_result(),
                    status_text=status_ref[0],
                ))
                time.sleep(frame_s)
                rotation += 0.08

            t.join()

            if interval_s <= 0 or stop.is_set():
                # Single-run: show final state for a moment then exit
                for _ in range(int(fps * 2)):
                    live.update(_build_display(
                        rotation=rotation,
                        cycle_result=_load_last_cycle_result(),
                        status_text=status_ref[0],
                    ))
                    time.sleep(frame_s)
                    rotation += 0.08
                break

            # ── Inter-cycle wait ──────────────────────────────────────────────
            last_result = _load_last_cycle_result()
            end = time.monotonic() + interval_s
            while time.monotonic() < end and not stop.is_set():
                remaining = int(end - time.monotonic())
                mins, secs = divmod(remaining, 60)
                live.update(_build_display(
                    rotation=rotation,
                    cycle_result=last_result,
                    status_text=f"Next cycle in  —  {mins:02d}:{secs:02d}",
                ))
                time.sleep(frame_s)
                rotation += 0.08


def _run_text_mode(interval_s: int = 0) -> None:
    """Fallback when rich is unavailable."""
    stop = threading.Event()
    _signal.signal(_signal.SIGTERM, lambda *_: stop.set())
    _signal.signal(_signal.SIGINT,  lambda *_: stop.set())

    cycle = 0
    while not stop.is_set():
        cycle += 1
        print(f"\n=== CYCLE {cycle} ===")
        try:
            _run_cycle_steps(lambda s: print(f"  {s}"))
        except _CycleFailed as exc:
            print(f"CYCLE {cycle} FAILED: {exc}")
        if interval_s <= 0 or stop.is_set():
            break
        print(f"Waiting {interval_s}s…")
        stop.wait(timeout=interval_s)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="SignalLogic — full observation cycle")
    ap.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECONDS",
        help="loop continuously, sleeping SECONDS between cycle completions (0 = run once)",
    )
    args = ap.parse_args()

    _run_with_helix(interval_s=args.loop)
