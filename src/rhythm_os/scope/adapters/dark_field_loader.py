"""
DARK FIELD → SCOPE ADAPTER

POSTURE: READ-ONLY OBSERVATION

- Reads sealed Waves from the Dark Field penstock
- Projects Wave fields directly (no payload decoding)
- No authority
- No mutation
- No inference
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime


# ---------------------------------------------------------------------
# WaveView-Compatible Projection
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class DarkFieldWaveView:
    t: float
    amplitude: float
    phase_spread: float
    buffer_margin: float
    persistence: int
    drift: Optional[float] = None
    afterglow: Optional[float] = None


# ---------------------------------------------------------------------
# Public Loader
# ---------------------------------------------------------------------


def load_penstock(penstock_dir: Path) -> Iterator[DarkFieldWaveView]:
    """
    Read all JSONL files in a penstock directory
    and yield read-only WaveView projections.
    """

    if not penstock_dir.exists():
        return iter(())

    def _iter() -> Iterator[DarkFieldWaveView]:
        for path in sorted(penstock_dir.glob("*.jsonl")):
            yield from _load_file(path)

    return _iter()


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------


def _load_file(path: Path) -> Iterator[DarkFieldWaveView]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except Exception:
                continue

            yield _project_wave(record)


def _project_wave(record: dict) -> DarkFieldWaveView:
    """
    Project a sealed Wave into a read-only WaveView.

    Coherence = amplitude (phase-lock carrier)
    Phase spread = stored phase
    """

    # Timestamp
    ts = record.get("timestamp")
    if isinstance(ts, str):
        try:
            t = datetime.fromisoformat(ts).timestamp()
        except Exception:
            t = 0.0
    else:
        t = 0.0

    # Phase spread (top-level phase)
    phase_spread = float(record.get("phase", 0.0))

    # Coherence = amplitude (0–1)
    amplitude = float(record.get("amplitude", 0.0))

    # Afterglow (stored as decay factor)
    afterglow = record.get("afterglow_decay")
    if afterglow is not None:
        afterglow = float(afterglow)

    return DarkFieldWaveView(
        t=t,
        amplitude=amplitude,
        phase_spread=phase_spread,
        buffer_margin=1.0,
        persistence=1,
        afterglow=afterglow,
    )
