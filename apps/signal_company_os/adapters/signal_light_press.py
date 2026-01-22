# apps/signal_company_os/adapters/signal_light_press.py

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Dict


def get_kernel_observables(lookback_hours: int = 24) -> Dict[str, float]:
    """
    Signal Light Press — Kernel observables (read-only).

    Produces descriptive proxies only.
    No thresholds. No interpretation. No posture.
    """

    # Locate codex directory (existing helper already in your tree)
    try:
        from apps.signal_company_os.codex.find_codex_dir import find_codex_dir
        codex_dir = find_codex_dir()
    except Exception:
        codex_dir = None

    now = datetime.now(timezone.utc)

    burst_count = 0
    latest_write = None

    if codex_dir and codex_dir.exists():
        for p in codex_dir.rglob("*.md"):
            try:
                mtime = datetime.fromtimestamp(
                    p.stat().st_mtime, tz=timezone.utc
                )
            except Exception:
                continue

            if (now - mtime).total_seconds() <= lookback_hours * 3600:
                burst_count += 1
                if latest_write is None or mtime > latest_write:
                    latest_write = mtime

    # Descriptive proxies only
    recovery_latency_hours = (
        (now - latest_write).total_seconds() / 3600
        if latest_write else float("inf")
    )

    variance_proxy = float(burst_count)

    return {
        "burst_frequency": float(burst_count),
        "recovery_latency_hours": recovery_latency_hours,
        "variance_proxy": variance_proxy,
    }
