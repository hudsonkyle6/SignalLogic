# apps/run_cycle_once.py
"""
ONE FULL SIGNAL CYCLE — BOUNDED OBSERVATION

Phase 1 Regime:
    - System pressure primary (REAL vitals)
    - Cyber cadence projection
    - Natural LIVE (Open-Meteo, 42.9876°N 71.8126°W)
    - Market muted

Temporal integrity preserved.
Core flow must continue.

Synthetic injectors DISABLED for baseline identity formation.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------
# UTF-8 TRANSPORT HARDENING
# ---------------------------------------------------------------------

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_ENV = os.environ.copy()
BASE_ENV["PYTHONUTF8"] = "1"
BASE_ENV["PYTHONIOENCODING"] = "utf-8"


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]  # SignalLogic/
PY = sys.executable

SYSTEM_OBS_WINDOW_S = 75
SCOPE_WINDOW_S = 10

ENABLE_NATURAL = True
ENABLE_MARKET = False
ENABLE_CYBER = True

# ---------------------------------------------------------------------
# Synthetic pressure DISABLED (Phase 1 hardening)
# ---------------------------------------------------------------------

ENABLE_PRESSURE = False
PRESSURE_PROFILE = "fragment_5s"
PRESSURE_MODULE = "apps.pressure_tools.net_pulse_injector"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

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


def prompt_scope(timeout_sec: int = 60) -> bool:
    import threading

    answer = {"value": None}

    def _ask():
        try:
            answer["value"] = input("\nRun Signal Scope? (Y/N): ").strip().lower()
        except Exception:
            pass

    t = threading.Thread(target=_ask, daemon=True)
    t.start()
    t.join(timeout_sec)
    return answer["value"] == "y"


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 72)
    print("=== BEGIN SIGNAL CYCLE ===")
    print("=" * 72)

    # ---------------------------------------------------------------
    # 1) SYSTEM OBSERVATION WINDOW (REAL VITALS ONLY)
    # ---------------------------------------------------------------

    print("\n--- SYSTEM OBSERVATION WINDOW ---")

    meter_proc = subprocess.Popen(
        [PY, "src/signal_core/core/instruments/hydro_meter.py"],
        cwd=str(ROOT),
        env=BASE_ENV,
    )

    pressure_proc = None
    if ENABLE_PRESSURE:
        pressure_proc = subprocess.Popen(
            [
                PY, "-m", PRESSURE_MODULE,
                "--duration", str(SYSTEM_OBS_WINDOW_S),
                "--profile", PRESSURE_PROFILE,
            ],
            cwd=str(ROOT),
            env=BASE_ENV,
        )

    try:
        countdown(SYSTEM_OBS_WINDOW_S, "SYSTEM METER WINDOW")
    finally:
        meter_proc.terminate()
        meter_proc.wait(timeout=10)

        if pressure_proc is not None:
            pressure_proc.terminate()
            pressure_proc.wait(timeout=10)

    print("--- SYSTEM OBSERVATION WINDOW CLOSED ---")

    # ---------------------------------------------------------------
    # 2) NATURAL (muted)
    # ---------------------------------------------------------------

    if ENABLE_NATURAL:
        natural_ok = run_module(
            "OBSERVATORY → NATURAL RAW",
            "apps.observatory_tools.emit_natural_raw_once",
            required=False
        )
        if natural_ok:
            run_module("PSR → NATURAL DOMAIN", "apps.psr_tools.emit_natural_domain", required=False)
            run_module("INGRESS → NATURAL", "apps.psr_tools.domain_to_natural_ingress", required=False)
    else:
        print("\nNATURAL METER: muted")

    # ---------------------------------------------------------------
    # 3) MARKET (muted)
    # ---------------------------------------------------------------

    if ENABLE_MARKET:
        market_ok = run_module(
            "OBSERVATORY → MARKET RAW",
            "apps.observatory_tools.emit_market_raw_once",
            required=False
        )
        if market_ok:
            domain_ok = run_module(
                "PSR → MARKET DOMAIN",
                "apps.psr_tools.observe_market_daily",
                required=False
            )
            if domain_ok:
                run_module(
                    "INGRESS → MARKET",
                    "apps.psr_tools.domain_to_market_ingress",
                    required=False
                )
    else:
        print("\nMARKET METER: muted")

    # ---------------------------------------------------------------
    # 3.5) CYBER
    # ---------------------------------------------------------------

    if ENABLE_CYBER:
        run_module("PSR → CYBER DOMAIN", "apps.psr_tools.emit_cyber_domain", required=False)
        run_module("INGRESS → CYBER", "apps.psr_tools.domain_to_cyber_ingress", required=False)
    else:
        print("\nCYBER: muted")

    # ---------------------------------------------------------------
    # 4) SYSTEM DOMAIN + INGRESS
    # ---------------------------------------------------------------

    run_module("PSR → SYSTEM DOMAIN", "apps.psr_tools.emit_system_domain", required=True)
    run_module("INGRESS → SYSTEM", "apps.psr_tools.domain_to_system_ingress", required=True)

    # ---------------------------------------------------------------
    # 5) HYDRO (REQUIRED)
    # ---------------------------------------------------------------

    run_module(
        "HYDRO → GATE / DISPATCH / COMMIT",
        "src.signal_core.core.hydro_run_daily",
        required=True
    )

    # ---------------------------------------------------------------
    # 6) TURBINE SUMMARY (READ-ONLY — closes observation loop)
    # ---------------------------------------------------------------

    run_module(
        "TURBINE → CONVERGENCE SUMMARY",
        "src.signal_core.core.hydro_turbine_summary",
        required=False
    )

    print("\n" + "=" * 72)
    print("=== END SIGNAL CYCLE ===")
    print("=" * 72)

    # ---------------------------------------------------------------
    # 7) OPTIONAL SCOPE
    # ---------------------------------------------------------------

    if prompt_scope(timeout_sec=60):
        print("\n" + "=" * 72)
        print("SCOPE → OBSERVATION (READ-ONLY)")
        print("=" * 72)

        scope_proc = subprocess.Popen(
            [PY, "src/rhythm_os/scope/scope_run_once.py"],
            cwd=str(ROOT),
            env=BASE_ENV,
        )

        try:
            countdown(SCOPE_WINDOW_S, "SCOPE WINDOW")
        finally:
            scope_proc.wait(timeout=10)

        print("SCOPE: COMPLETE")
    else:
        print("\nSCOPE: skipped")


if __name__ == "__main__":
    main()
