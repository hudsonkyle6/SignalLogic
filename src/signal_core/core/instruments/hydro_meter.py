# rhythm_os/core/instruments/hydro_meter.py
"""
Hydro Meter — Sovereign Flow Instrument (Local-first)

Purpose:
    - Observe local "flow meters" (network, process, CPU frequency).
    - Emit append-only JSONL packets for downstream Rhythm OS ingestion.
    - NO alerts. NO optimization actions. NO health judgments.
    - Pressure telemetry only.

Design:
    - Sample -> normalize -> emit
    - Deterministic fields per sample window
    - Stable extractor metadata
"""

from __future__ import annotations

import json
import os
import signal
import threading
import time
import math
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple

import psutil  # pip install psutil

from signal_core.core.log import configure, get_logger

configure()
log = get_logger(__name__)


# ==============================================================================
# CONFIG
# ==============================================================================

DEFAULT_INTERVAL_S = 2.0
DEFAULT_WINDOW_S = 60.0
DEFAULT_MIN_POINTS = 10

from rhythm_os.runtime.paths import METERS_DIR as DEFAULT_OUT_DIR


# ==============================================================================
# UTIL
# ==============================================================================

def utc_iso(ts: Optional[float] = None) -> str:
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")

def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    # append-only; do not rewrite
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n")

def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0

def stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(v)

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ==============================================================================
# PACKET (meter_wave)
# ==============================================================================

@dataclass(frozen=True)
class MeterPacket:
    t: float
    lane: str                  # e.g. "net", "proc", "cpu"
    channel: str               # e.g. "iface:Ethernet", "proc:python", "cpu:freq"
    window_s: float
    data: Dict[str, Any]
    extractor: Dict[str, Any]  # provenance; stable fields

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t": self.t,
            "domain": "core",
            "lane": self.lane,
            "channel": self.channel,
            "window_s": self.window_s,
            "data": self.data,
            "extractor": self.extractor,
        }


# ==============================================================================
# BASE METER
# ==============================================================================

class BaseMeter:
    lane: str

    def __init__(self, interval_s: float, window_s: float, min_points: int) -> None:
        self.interval_s = float(interval_s)
        self.window_s = float(window_s)
        self.min_points = int(min_points)

        self._points: List[Tuple[float, Dict[str, float]]] = []  # (t, raw)
        self._max_points = max(1, int(self.window_s / self.interval_s) + 3)

    def sample_raw(self) -> Optional[Dict[str, float]]:
        raise NotImplementedError

    def channel_name(self) -> str:
        raise NotImplementedError

    def push_sample(self, t: float, raw: Dict[str, float]) -> None:
        self._points.append((t, raw))
        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points :]

    def window_points(self) -> List[Tuple[float, Dict[str, float]]]:
        if not self._points:
            return []
        cutoff = self._points[-1][0] - self.window_s
        return [(t, r) for (t, r) in self._points if t >= cutoff]

    def compute(self) -> Optional[Dict[str, Any]]:
        pts = self.window_points()
        if len(pts) < self.min_points:
            return None
        return self._compute_from_points(pts)

    def _compute_from_points(self, pts: List[Tuple[float, Dict[str, float]]]) -> Dict[str, Any]:
        raise NotImplementedError


# ==============================================================================
# LANE 1: Network Interface Meter
# ==============================================================================

class NetIfaceMeter(BaseMeter):
    lane = "net"

    def __init__(self, iface: str, interval_s: float, window_s: float, min_points: int) -> None:
        super().__init__(interval_s, window_s, min_points)
        self.iface = iface
        self._last = psutil.net_io_counters(pernic=True).get(iface)
        self._last_t = time.time()

    def channel_name(self) -> str:
        return f"iface:{self.iface}"

    def sample_raw(self) -> Optional[Dict[str, float]]:
        now = time.time()
        io = psutil.net_io_counters(pernic=True).get(self.iface)
        if io is None or self._last is None:
            self._last = io
            self._last_t = now
            return None

        dt = max(1e-6, now - self._last_t)
        d_in = float(io.bytes_recv - self._last.bytes_recv)
        d_out = float(io.bytes_sent - self._last.bytes_sent)

        self._last = io
        self._last_t = now

        # raw increments; rates computed over window
        return {"dt": dt, "bytes_in": d_in, "bytes_out": d_out}

    def _compute_from_points(self, pts: List[Tuple[float, Dict[str, float]]]) -> Dict[str, Any]:
        dts = [r["dt"] for _, r in pts if r.get("dt") is not None]
        ins = [r["bytes_in"] for _, r in pts]
        outs = [r["bytes_out"] for _, r in pts]

        total_dt = sum(dts) if dts else self.window_s
        in_rate_bps = (sum(ins) / max(1e-6, total_dt)) * 8.0
        out_rate_bps = (sum(outs) / max(1e-6, total_dt)) * 8.0

        # turbidity proxy = variability of per-sample increments
        turb_in = stdev(ins)
        turb_out = stdev(outs)

        direction_bias = out_rate_bps / (in_rate_bps + 1e-6)

        return {
            "n": len(pts),
            "in_rate_bps": in_rate_bps,
            "out_rate_bps": out_rate_bps,
            "direction_bias": direction_bias,
            "turbidity_in": turb_in,
            "turbidity_out": turb_out,
        }


# ==============================================================================
# LANE 2: Process Meter (per-process CPU + IO counters)
# ==============================================================================

class ProcMeter(BaseMeter):
    lane = "proc"

    def __init__(self, proc_name: str, interval_s: float, window_s: float, min_points: int) -> None:
        super().__init__(interval_s, window_s, min_points)
        self.proc_name = proc_name.lower()
        self._last: Dict[int, Dict[str, float]] = {}  # pid -> last counters
        self._last_t = time.time()

    def channel_name(self) -> str:
        return f"proc:{self.proc_name}"

    def _match_procs(self) -> List[psutil.Process]:
        procs: List[psutil.Process] = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                nm = (p.info.get("name") or "").lower()
                if nm and self.proc_name in nm:
                    procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    def sample_raw(self) -> Optional[Dict[str, float]]:
        now = time.time()
        dt = max(1e-6, now - self._last_t)
        self._last_t = now

        procs = self._match_procs()
        if not procs:
            # still emit "silence" by returning None; no packet generated this cycle
            self._last = {}
            return None

        cpu_s = 0.0
        read_b = 0.0
        write_b = 0.0
        rss_b = 0.0

        new_last: Dict[int, Dict[str, float]] = {}

        for p in procs:
            try:
                pid = p.pid
                cpu_times = p.cpu_times()
                cpu_total = float(cpu_times.user + cpu_times.system)

                io = p.io_counters() if hasattr(p, "io_counters") else None
                rb = float(getattr(io, "read_bytes", 0.0)) if io else 0.0
                wb = float(getattr(io, "write_bytes", 0.0)) if io else 0.0

                mem = p.memory_info()
                rss = float(getattr(mem, "rss", 0.0))

                prev = self._last.get(pid)
                if prev:
                    cpu_s += max(0.0, cpu_total - prev["cpu_total"])
                    read_b += max(0.0, rb - prev["rb"])
                    write_b += max(0.0, wb - prev["wb"])
                else:
                    # first sighting -> no delta
                    pass

                rss_b += rss
                new_last[pid] = {"cpu_total": cpu_total, "rb": rb, "wb": wb}

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self._last = new_last

        return {
            "dt": dt,
            "cpu_s": cpu_s,
            "read_b": read_b,
            "write_b": write_b,
            "rss_b": rss_b,
            "proc_count": float(len(procs)),
        }

    def _compute_from_points(self, pts: List[Tuple[float, Dict[str, float]]]) -> Dict[str, Any]:
        dts = [r["dt"] for _, r in pts]
        total_dt = sum(dts) if dts else self.window_s

        cpu_s = [r["cpu_s"] for _, r in pts]
        read_b = [r["read_b"] for _, r in pts]
        write_b = [r["write_b"] for _, r in pts]
        rss_b = [r["rss_b"] for _, r in pts]
        proc_counts = [r["proc_count"] for _, r in pts]

        cpu_rate = sum(cpu_s) / max(1e-6, total_dt)      # CPU-seconds per second (≈ cores used)
        read_rate = sum(read_b) / max(1e-6, total_dt)
        write_rate = sum(write_b) / max(1e-6, total_dt)

        return {
            "n": len(pts),
            "proc_count_mean": mean(proc_counts),
            "cpu_rate_core_equiv": cpu_rate,
            "read_rate_Bps": read_rate,
            "write_rate_Bps": write_rate,
            "rss_bytes_mean": mean(rss_b),
            "turbidity_cpu": stdev(cpu_s),
            "turbidity_io": stdev([a + b for a, b in zip(read_b, write_b)]),
        }


# ==============================================================================
# LANE 3: CPU Frequency Meter (pressure telemetry only)
# ==============================================================================

class CpuFreqMeter(BaseMeter):
    lane = "cpu"

    def __init__(self, interval_s: float, window_s: float, min_points: int) -> None:
        super().__init__(interval_s, window_s, min_points)

    def channel_name(self) -> str:
        return "cpu:freq"

    def sample_raw(self) -> Optional[Dict[str, float]]:
        freq = psutil.cpu_freq()
        if freq is None:
            return None
        # psutil reports MHz
        return {
            "cur_mhz": float(freq.current),
            "min_mhz": float(freq.min) if freq.min else 0.0,
            "max_mhz": float(freq.max) if freq.max else 0.0,
        }

    def _compute_from_points(self, pts: List[Tuple[float, Dict[str, float]]]) -> Dict[str, Any]:
        cur = [r["cur_mhz"] for _, r in pts]
        mn = [r["min_mhz"] for _, r in pts]
        mx = [r["max_mhz"] for _, r in pts]

        cur_mean = mean(cur)
        cur_sd = stdev(cur)

        # Normalize to [0,1] if min/max available, else None
        min_mean = mean(mn)
        max_mean = mean(mx)
        norm = None
        if max_mean > min_mean and min_mean > 0:
            norm = clamp01((cur_mean - min_mean) / (max_mean - min_mean))

        return {
            "n": len(pts),
            "cur_mhz_mean": cur_mean,
            "cur_mhz_sd": cur_sd,
            "min_mhz_mean": min_mean,
            "max_mhz_mean": max_mean,
            "cur_norm_0_1": norm,  # pressure proxy only, not a health score
        }

# ==============================================================================
# LANE 4: CPU Utilization Meter (pressure envelope only)
# ==============================================================================

class CpuUtilMeter(BaseMeter):
    lane = "cpu"

    def __init__(self, interval_s: float, window_s: float, min_points: int) -> None:
        super().__init__(interval_s, window_s, min_points)

    def channel_name(self) -> str:
        return "cpu:util"

    def sample_raw(self) -> Optional[Dict[str, float]]:
        # Non-blocking instantaneous utilization
        util = psutil.cpu_percent(interval=None)
        return {"cpu_percent": float(util)}

    def _compute_from_points(
        self,
        pts: List[Tuple[float, Dict[str, float]]]
    ) -> Dict[str, Any]:

        util = [r["cpu_percent"] for _, r in pts]

        util_mean = mean(util)
        util_sd = stdev(util) if len(util) > 1 else 0.0

        # Envelope: high-pressure edge (95th percentile)
        util_sorted = sorted(util)
        p95_idx = max(0, int(len(util_sorted) * 0.95) - 1)
        util_p95 = util_sorted[p95_idx]

        return {
            "n": len(pts),
            "cpu_percent_mean": util_mean,
            "cpu_percent_sd": util_sd,          # vibration / turbulence proxy
            "cpu_envelope_high": util_p95,      # sustained pressure ceiling
        }

# ==============================================================================
# RUNNER
# ==============================================================================

def build_meters(
    interval_s: float,
    window_s: float,
    min_points: int,
    ifaces: Optional[List[str]],
    proc_names: Optional[List[str]],
) -> List[BaseMeter]:
    meters: List[BaseMeter] = []

    # Network meters
    stats = psutil.net_if_stats()
    active_ifaces = list(stats.keys())

    if ifaces:
        for iface in ifaces:
            if iface in stats:
                meters.append(NetIfaceMeter(iface, interval_s, window_s, min_points))
    else:
        # best effort: include "up" interfaces
        for iface, st in stats.items():
            if st.isup:
                meters.append(NetIfaceMeter(iface, interval_s, window_s, min_points))

    # Process meters
    if proc_names:
        for name in proc_names:
            meters.append(ProcMeter(name, interval_s, window_s, min_points))

    # CPU freq meter
    meters.append(CpuFreqMeter(interval_s, window_s, min_points))

    return meters


def emit_packets(
    meters: List[BaseMeter],
    out_dir: Path,
    runner: str = "hydro_meter",
    version: str = "v1",
    stop_event: Optional[threading.Event] = None,
) -> None:
    if stop_event is None:
        stop_event = threading.Event()

    safe_mkdir(out_dir)

    host = platform.node() or "unknown_host"
    os_name = platform.system().lower()

    log.info("hydro_meter started out_dir=%s interval=%.1fs", out_dir, meters[0].interval_s if meters else DEFAULT_INTERVAL_S)

    while not stop_event.is_set():
        t0 = time.time()

        for m in meters:
            raw = m.sample_raw()
            if raw is not None:
                m.push_sample(t0, raw)

            computed = m.compute()
            if computed is None:
                # silence while warming or unavailable
                continue

            pkt = MeterPacket(
                t=t0,
                lane=m.lane,
                channel=m.channel_name(),
                window_s=m.window_s,
                data=computed,
                extractor={
                    "source": "hydro_meter",
                    "runner": runner,
                    "version": version,
                    "host": host,
                    "os": os_name,
                    "interval_s": m.interval_s,
                    "window_s": m.window_s,
                },
            ).to_dict()

            # One file per day (append-only)
            day = datetime.fromtimestamp(t0, tz=timezone.utc).strftime("%Y-%m-%d")
            path = out_dir / f"{day}.jsonl"
            append_jsonl(path, pkt)

        # interval control — use stop_event.wait() so SIGTERM wakes us immediately
        dt = time.time() - t0
        sleep_s = max(0.0, meters[0].interval_s - dt) if meters else DEFAULT_INTERVAL_S
        stop_event.wait(timeout=sleep_s)

    log.info("hydro_meter stopped")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Hydro Meter (local flow instrument)")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S, help="sample interval seconds")
    ap.add_argument("--window", type=float, default=DEFAULT_WINDOW_S, help="rolling window seconds")
    ap.add_argument("--min-points", type=int, default=DEFAULT_MIN_POINTS, help="min points before emitting")
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT_DIR), help="output directory (append-only)")
    ap.add_argument("--ifaces", type=str, default="", help="comma list of interfaces (default: all up)")
    ap.add_argument("--procs", type=str, default="python,git,node", help="comma list of process name substrings")
    args = ap.parse_args()

    ifaces = [s.strip() for s in args.ifaces.split(",") if s.strip()] or None
    procs = [s.strip() for s in args.procs.split(",") if s.strip()] or None

    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())

    meters = build_meters(args.interval, args.window, args.min_points, ifaces, procs)
    emit_packets(meters, Path(args.out), stop_event=stop_event)


if __name__ == "__main__":
    main()
