"""
Runtime Bus Utilities (tolerant, append-only)

AUTHORITY: Signal Light Press
CLASSIFICATION: RUNTIME SUPPORT
EXECUTABLE: NO (library)
DECISION AUTHORITY: NONE

- Loads DomainWaves from JSONL bus files
- Ignores malformed lines (never rewrites history)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rhythm_os.psr.domain_wave import DomainWave


def today_bus_file(*, bus_dir: Path, t_ref: float) -> Path:
    date_str = time.strftime("%Y-%m-%d", time.localtime(t_ref))
    return bus_dir / f"{date_str}.jsonl"


def _iter_bus_lines(files: List[Path]) -> Sequence[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            with f.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Append-only bus: malformed lines are ignored, not corrected.
                        continue
        except FileNotFoundError:
            continue
    return out


def load_recent_domain_waves(
    *,
    bus_dir: Path,
    t_ref: float,
    history_window_sec: float,
) -> List[DomainWave]:
    """
    Verbatim load of recent DomainWave records from bus_dir/*.jsonl.

    - best effort parse
    - no mutation
    - skips malformed lines
    """
    if not bus_dir.exists():
        return []

    files = sorted(bus_dir.glob("*.jsonl"))
    if not files:
        return []

    raw = _iter_bus_lines(files)

    out: List[DomainWave] = []
    for rec in raw:
        try:
            t = float(rec.get("t"))
        except Exception:
            continue

        if abs(t - t_ref) > history_window_sec:
            continue

        try:
            dw = DomainWave(
                t=float(rec["t"]),
                domain=str(rec["domain"]),
                channel=str(rec["channel"]),
                field_cycle=str(rec.get("field_cycle", "unknown")),
                phase_external=float(rec.get("phase_external", 0.0)),
                phase_field=float(rec.get("phase_field", 0.0)),
                phase_diff=float(rec.get("phase_diff", 0.0)),
                coherence=rec.get("coherence", None),
                extractor=dict(rec.get("extractor", {})),
            )
        except Exception:
            continue

        out.append(dw)

    out.sort(key=lambda w: float(w.t))
    return out

def has_emission_at_time(
    *,
    bus_dir: Path,
    t_ref: float,
    domain: str,
    channel: str,
) -> bool:
    """
    Returns True if a DomainWave with the same (t, domain, channel)
    already exists on the bus.

    Read-only. Best-effort. No mutation.
    """
    if not bus_dir.exists():
        return False

    for f in sorted(bus_dir.glob("*.jsonl")):
        try:
            with f.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    if (
                        float(rec.get("t", -1)) == float(t_ref)
                        and rec.get("domain") == domain
                        and rec.get("channel") == channel
                    ):
                        return True
        except FileNotFoundError:
            continue

    return False
