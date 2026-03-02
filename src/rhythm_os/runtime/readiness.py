"""
Deployment readiness checker.

Counts today's baseline records for each signature tier and returns
a structured ReadinessStatus. The system always runs — readiness is
informational, not a gate. The dashboard and CycleResult surface it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rhythm_os.runtime.paths import METERS_DIR, NATURAL_DIR


@dataclass
class ReadinessStatus:
    system_count: int  # meter records written today
    natural_count: int  # natural records written today
    min_meter_cycles: int  # threshold from deployment manifest
    min_natural_records: int
    system_ready: bool
    natural_ready: bool
    overall_ready: bool  # both tiers are warm

    def summary(self) -> str:
        parts = []
        parts.append(
            f"system={'WARM' if self.system_ready else f'cold({self.system_count}/{self.min_meter_cycles})'}"
        )
        parts.append(
            f"natural={'WARM' if self.natural_ready else f'cold({self.natural_count}/{self.min_natural_records})'}"
        )
        return "  ".join(parts)


def _count_today_records(data_dir: Path) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = data_dir / f"{today}.jsonl"
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def check_readiness(
    min_meter_cycles: int = 30,
    min_natural_records: int = 4,
) -> ReadinessStatus:
    """Check whether each signature tier has sufficient baseline data today."""
    system_count = _count_today_records(METERS_DIR)
    natural_count = _count_today_records(NATURAL_DIR)
    system_ready = system_count >= min_meter_cycles
    natural_ready = natural_count >= min_natural_records
    return ReadinessStatus(
        system_count=system_count,
        natural_count=natural_count,
        min_meter_cycles=min_meter_cycles,
        min_natural_records=min_natural_records,
        system_ready=system_ready,
        natural_ready=natural_ready,
        overall_ready=system_ready and natural_ready,
    )
