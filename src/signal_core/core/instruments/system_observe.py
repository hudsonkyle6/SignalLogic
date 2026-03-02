"""
System Observer — single-snapshot system signature.

Produces one HydroPacket per call from a direct psutil read.
No rolling window — that is hydro_meter's job.
This module provides the per-cycle system pulse that run_cycle_once() emits.

Falls back to a minimal bootstrap packet when psutil is unavailable.
"""

from __future__ import annotations

import platform
import time
import uuid
from typing import Any, Dict

from signal_core.core.hydro_types import HydroPacket

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def sample_once() -> HydroPacket:
    """
    Take a single system-metrics snapshot and return a HydroPacket.

    Fields:
        cpu_percent    — 0–100, 0.1s blocking interval for accuracy
        mem_percent    — virtual memory used %
        cpu_mhz        — current CPU frequency (0.0 if unavailable)
        net_bytes_sent — cumulative sent since boot (delta tracking is
                         left to hydro_meter's rolling window)
        net_bytes_recv — cumulative recv since boot
        coherence      — 1 - max(cpu%, mem%)/100 → pressure proxy

    Coherence interpretation: high system load → lower coherence →
    packets carry weaker signal during noisy conditions.
    """
    t_now = time.time()

    if not _HAS_PSUTIL:
        return _bootstrap_packet(t_now)

    try:
        cpu_pct = float(_psutil.cpu_percent(interval=0.1))
        mem = _psutil.virtual_memory()
        mem_pct = float(mem.percent)

        freq = _psutil.cpu_freq()
        cpu_mhz = float(freq.current) if freq else 0.0

        net = _psutil.net_io_counters()
        net_sent = int(net.bytes_sent) if net else 0
        net_recv = int(net.bytes_recv) if net else 0

        coherence = _clamp01(1.0 - max(cpu_pct, mem_pct) / 100.0)

        value: Dict[str, Any] = {
            "cpu_percent": cpu_pct,
            "mem_percent": mem_pct,
            "cpu_mhz": cpu_mhz,
            "net_bytes_sent": net_sent,
            "net_bytes_recv": net_recv,
            "coherence": coherence,
        }

        return HydroPacket(
            t=t_now,
            packet_id=str(uuid.uuid4()),
            lane="system",
            domain="core",
            channel="system_metrics",
            value=value,
            provenance={
                "source": "system_observe",
                "host": platform.node(),
                "os": platform.system().lower(),
            },
            rate=_clamp01(cpu_pct / 100.0),
            anomaly_flag=cpu_pct > 90.0 or mem_pct > 90.0,
            replay=False,
        )

    except Exception:
        return _bootstrap_packet(t_now)


def _bootstrap_packet(t_now: float) -> HydroPacket:
    """Minimal packet when psutil is unavailable or sampling fails."""
    return HydroPacket(
        t=t_now,
        packet_id=str(uuid.uuid4()),
        lane="system",
        domain="core",
        channel="bootstrap",
        value={"coherence": 0.5, "psutil_available": _HAS_PSUTIL},
        provenance={"source": "system_observe_fallback"},
        rate=0.0,
        anomaly_flag=False,
        replay=False,
    )
