#!/usr/bin/env python3
"""
CHAOS INJECTOR — METER-SIDE PRESSURE (DEFENSIVE)

POSTURE:
- OBSERVATORY-SIDE ONLY (writes to meters/)
- NO PENSTOCK TOUCH
- BOUNDED: duration + max_lines
- Purpose: reveal brittle assumptions safely (parsing, timing, replay, extremes)

Emits a mixed stream of:
- valid net packets with multi-frequency modulation
- timestamp jitter + occasional out-of-order sample
- replay duplicates
- sparse "corrupt" lines (invalid JSON)
- sparse "missing field" records (valid JSON but structurally incomplete)
- occasional extreme out_rate spikes

This is NOT an attack tool; it is controlled fault injection for your own pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone


METERS_DIR = Path("src/rhythm_os/data/dark_field/meters")


@dataclass(frozen=True)
class ChaosConfig:
    duration_s: float
    rate_hz: float
    max_lines: int

    base_bps: float
    noise_frac: float

    jitter_ms: float
    out_of_order_every: int

    replay_every: int
    corrupt_every: int
    missing_every: int
    extreme_every: int

    lanes: tuple[str, ...]


def _utc_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_float(x: float) -> float:
    try:
        if math.isnan(x) or math.isinf(x):
            return 0.0
    except Exception:
        return 0.0
    return float(x)


def _multifreq_signal(t: float) -> float:
    """
    Multi-frequency modulation: 1s + 5s + 17s blended.
    Output is roughly in [0, ~3] range before scaling.
    """
    s1 = 1.0 + math.sin(2 * math.pi * t / 1.0)
    s5 = 1.0 + 0.5 * math.sin(2 * math.pi * t / 5.0)
    s17 = 1.0 + 0.25 * math.sin(2 * math.pi * t / 17.0)
    return s1 + s5 + s17


def _write_line(f, line: str) -> None:
    f.write(line)
    f.write("\n")
    # flush so the meter reader sees it immediately during the window
    f.flush()
    os.fsync(f.fileno())


def _emit_valid_packet(t: float, out_bps: float, lane: str) -> dict:
    return {
        "t": _safe_float(t),
        "domain": "core",  # optional; some meters include it
        "lane": lane,
        "channel": "iface:CHAOS",
        "window_s": 60.0,  # optional; safe default
        "data": {
            "n": 1,
            "in_rate_bps": 0.0,
            "out_rate_bps": _safe_float(out_bps),
            "direction_bias": 0.0,
            "turbidity_in": 0.0,
            "turbidity_out": 0.0,
        },
        "extractor": {
            "source": "chaos_injector",
            "runner": "chaos_injector",
            "version": "v1",
            "host": os.environ.get("COMPUTERNAME") or "unknown",
            "os": os.name,
            "interval_s": 1.0,
            "window_s": 60.0,
        },
    }


def run_all_profiles(cfg: ChaosConfig) -> int:
    METERS_DIR.mkdir(parents=True, exist_ok=True)

    out_path = METERS_DIR / f"chaos_{_utc_tag()}.jsonl"
    print(f"CHAOS: writing → {out_path}")

    dt = 1.0 / max(cfg.rate_hz, 0.1)
    start = time.time()
    last_packets: list[str] = []

    lines = 0
    i = 0

    with out_path.open("w", encoding="utf-8") as f:
        while True:
            now = time.time()
            if (now - start) >= cfg.duration_s:
                break
            if lines >= cfg.max_lines:
                break

            i += 1

            # -----------------------------
            # Timing turbulence: jitter
            # -----------------------------
            jitter = (random.random() - 0.5) * 2.0 * (cfg.jitter_ms / 1000.0)
            t = now + jitter

            # occasional out-of-order sample
            if cfg.out_of_order_every > 0 and (i % cfg.out_of_order_every == 0):
                t = t - random.uniform(0.2, 2.0)

            # -----------------------------
            # Choose lane
            # -----------------------------
            lane = random.choice(cfg.lanes)

            # -----------------------------
            # Capacity-ish pressure: high density stream (rate_hz)
            # Data pressure: multifrequency + noise
            # -----------------------------
            mod = _multifreq_signal(t)
            noise = 1.0 + cfg.noise_frac * (random.random() - 0.5) * 2.0
            out_bps = cfg.base_bps * mod * noise

            # occasional extreme spike
            if cfg.extreme_every > 0 and (i % cfg.extreme_every == 0):
                out_bps = out_bps * random.choice([10.0, 50.0, 100.0])

            # -----------------------------
            # Data integrity turbulence
            # -----------------------------
            # corrupt line (invalid JSON)
            if cfg.corrupt_every > 0 and (i % cfg.corrupt_every == 0):
                _write_line(f, "{this is not valid json")
                lines += 1
                time.sleep(dt)
                continue

            # missing-field record (valid JSON, structurally incomplete)
            if cfg.missing_every > 0 and (i % cfg.missing_every == 0):
                missing = {"t": t, "lane": lane, "data": {"out_rate_bps": out_bps}}
                # randomly remove critical keys
                if random.random() < 0.5:
                    missing.pop("data", None)
                _write_line(f, json.dumps(missing, ensure_ascii=False))
                lines += 1
                time.sleep(dt)
                continue

            # valid packet
            pkt = _emit_valid_packet(t=t, out_bps=out_bps, lane=lane)
            line = json.dumps(pkt, ensure_ascii=False)

            # replay duplicate
            if cfg.replay_every > 0 and (i % cfg.replay_every == 0) and last_packets:
                _write_line(f, random.choice(last_packets))
                lines += 1

            _write_line(f, line)
            last_packets.append(line)
            if len(last_packets) > 250:
                last_packets = last_packets[-250:]

            lines += 1
            time.sleep(dt)

    print(f"CHAOS: complete (lines={lines})")
    return lines


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bounded chaos injector (defensive).")
    p.add_argument("--duration", type=float, default=75.0)
    p.add_argument("--rate-hz", type=float, default=20.0)
    p.add_argument("--max-lines", type=int, default=5000)

    p.add_argument("--base-bps", type=float, default=250_000.0)
    p.add_argument("--noise-frac", type=float, default=0.10)

    p.add_argument("--jitter-ms", type=float, default=35.0)
    p.add_argument("--out-of-order-every", type=int, default=97)

    p.add_argument("--replay-every", type=int, default=29)
    p.add_argument("--corrupt-every", type=int, default=113)
    p.add_argument("--missing-every", type=int, default=71)
    p.add_argument("--extreme-every", type=int, default=157)

    p.add_argument("--lanes", type=str, default="net",
                   help="Comma-separated lanes to emit into (default: net)")
    return p


def main() -> None:
    args = build_parser().parse_args()
    lanes = tuple([x.strip() for x in args.lanes.split(",") if x.strip()]) or ("net",)

    cfg = ChaosConfig(
        duration_s=float(args.duration),
        rate_hz=float(args.rate_hz),
        max_lines=int(args.max_lines),
        base_bps=float(args.base_bps),
        noise_frac=float(args.noise_frac),
        jitter_ms=float(args.jitter_ms),
        out_of_order_every=int(args.out_of_order_every),
        replay_every=int(args.replay_every),
        corrupt_every=int(args.corrupt_every),
        missing_every=int(args.missing_every),
        extreme_every=int(args.extreme_every),
        lanes=lanes,
    )
    run_all_profiles(cfg)


if __name__ == "__main__":
    main()
