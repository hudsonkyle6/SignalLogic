#!/usr/bin/env python3
"""
NET PULSE INJECTOR (BENIGN LOAD + IMBALANCE MODES)

POSTURE:
- TEST HARNESS ONLY
- WRITES SYNTHETIC METER PACKETS (lane=net) INTO METERS_DIR
- DOES NOT TOUCH INGRESS DIRECTLY
- DOES NOT MODIFY EXISTING FILES
- APPEND-ONLY EMISSION
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


METERS_DIR = Path("src/rhythm_os/data/dark_field/meters")


# --- add imports at top ---
import random

# --- extend Profile ---
@dataclass(frozen=True)
class Profile:
    name: str
    base_bps: float
    pulse_bps: float
    pulse_period_s: float
    jitter_frac: float
    interval_s: float

    # fragmentation controls (defaults for existing profiles)
    sources: int = 1
    period_jitter_frac: float = 0.0     # per-source period perturbation
    phase_offsets: tuple[float, ...] = ()  # radians, len>=sources optional
    ts_jitter_ms: float = 0.0
    out_of_order_every: int = 0         # every N emits, step timestamp backwards
    out_of_order_backstep_s: float = 0.0


# --- add new profile ---
PROFILES = {
    "pulse_1s": Profile(
        name="pulse_1s",
        base_bps=200_000,
        pulse_bps=800_000,
        pulse_period_s=1.0,
        jitter_frac=0.02,
        interval_s=0.02,
    ),

    "pulse_5s": Profile(
        name="pulse_5s",
        base_bps=200_000,
        pulse_bps=1_200_000,
        pulse_period_s=5.0,
        jitter_frac=0.02,
        interval_s=0.02,
    ),

    "burst": Profile(
        name="burst",
        base_bps=100_000,
        pulse_bps=2_000_000,
        pulse_period_s=0.5,
        jitter_frac=0.05,
        interval_s=0.05,
    ),

    # 🔥 Phase fragmentation profile
    "fragment_5s": Profile(
        name="fragment_5s",
        base_bps=300_000,
        pulse_bps=1_000_000,
        pulse_period_s=5.0,
        jitter_frac=0.25,
        interval_s=0.02,

        sources=3,
        period_jitter_frac=0.1,
        ts_jitter_ms=20.0,
    ),

}



# -------------------------
# Helpers
# -------------------------

def _now() -> float:
    return time.time()


def _jitter(mult: float, frac: float, t: float) -> float:
    if frac <= 0:
        return mult
    j = (math.sin(t * 7.31) + math.cos(t * 3.17)) * 0.5
    return mult * (1.0 + frac * j)


# -------------------------
# Waveform Generators
# -------------------------

def wave_sine(t: float, period: float) -> float:
    return 0.5 * (1.0 + math.sin(2.0 * math.pi * t / period))


def wave_rectified(t: float, period: float) -> float:
    raw = math.sin(2.0 * math.pi * t / period)
    return max(0.0, raw)  # half-wave rectified


def wave_dual(t: float) -> float:
    s5 = 0.5 * (1.0 + math.sin(2.0 * math.pi * t / 5.0))
    s1 = 0.5 * (1.0 + math.sin(2.0 * math.pi * t / 1.0))
    return 0.7 * s5 + 0.3 * s1


def wave_step(t: float, start: float) -> float:
    elapsed = t - start
    if elapsed < 20:
        return 0.2
    elif elapsed < 40:
        return 1.0
    else:
        return 0.3


# -------------------------
# Emission
# -------------------------

def emit_for(duration_s: float, profile: Profile) -> Path:
    METERS_DIR.mkdir(parents=True, exist_ok=True)

    host = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown-host"
    run_id = uuid4().hex[:10]
    out_path = METERS_DIR / f"sim_net_pressure_{profile.name}_{run_id}.jsonl"

    # build per-source periods + phase offsets
    src_n = max(1, int(profile.sources))
    periods = []
    offsets = []
    for k in range(src_n):
        pj = profile.period_jitter_frac
        p = profile.pulse_period_s * (1.0 + (random.random() * 2 - 1) * pj) if pj > 0 else profile.pulse_period_s
        periods.append(p)
        if profile.phase_offsets and k < len(profile.phase_offsets):
            offsets.append(profile.phase_offsets[k])
        else:
            offsets.append((2.0 * math.pi / src_n) * k)

    start = _now()
    n = 0
    i = 0

    with out_path.open("w", encoding="utf-8") as f:
        while (_now() - start) < duration_s:
            i += 1

            # base timestamp
            t = _now()

            # timestamp jitter (ms-scale)
            if profile.ts_jitter_ms > 0:
                t += (random.random() * 2 - 1) * (profile.ts_jitter_ms / 1000.0)

            # occasional out-of-order
            if profile.out_of_order_every and (i % profile.out_of_order_every == 0):
                t -= profile.out_of_order_backstep_s

            # pick source (interleave competing clocks)
            src = i % src_n
            period = periods[src]
            phi0 = offsets[src]

            # sinusoid in [0,1] with phase offset per source
            s = 0.5 * (1.0 + math.sin(phi0 + 2.0 * math.pi * t / period))
            out_bps = profile.base_bps + profile.pulse_bps * s
            out_bps = _jitter(out_bps, profile.jitter_frac, t)

            pkt = {
                "t": t,
                "domain": "core",
                "lane": "net",
                "channel": f"sim:{profile.name}:src{src}:{host}",
                "window_s": None,
                "data": {
                    "n": 1,
                    "in_rate_bps": 0.0,
                    "out_rate_bps": float(out_bps),
                    "direction_bias": 1.0,
                    "turbidity_in": 0.0,
                    "turbidity_out": 0.0,
                },
                "extractor": {
                    "source": "pressure_injector",
                    "runner": "net_pulse_injector",
                    "version": "v1",
                    "host": host,
                    "interval_s": profile.interval_s,
                    "profile": profile.name,
                    "run_id": run_id,
                    "src_n": src_n,
                    "periods": periods,   # ok to log: defensive provenance
                },
            }

            f.write(json.dumps(pkt, separators=(",", ":"), ensure_ascii=False) + "\n")
            f.flush()

            n += 1
            time.sleep(profile.interval_s)

    print(f"PRESSURE: emitted {n} synthetic net packets -> {out_path}")
    return out_path



# -------------------------
# Main
# -------------------------

def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=75.0)
    p.add_argument(
        "--profile",
        type=str,
        default="pulse_1s",
        choices=sorted(PROFILES.keys()),
    )
    args = p.parse_args()

    profile = PROFILES[args.profile]
    emit_for(args.duration, profile)

if __name__ == "__main__":
    main()
