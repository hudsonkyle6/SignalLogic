"""
DARK FIELD → SCOPE ADAPTER

POSTURE: READ-ONLY OBSERVATION

This module:
- Reads sealed Waves from the Dark Field
- Exposes WaveView-compatible objects
- Performs no interpretation, filtering, or inference
- Owns no authority and introduces no state
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional


# ---------------------------------------------------------------------
# WaveView-Compatible Projection
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class DarkFieldWaveView:
    """
    Minimal projection of a sealed Wave for scope rendering.
    """

    t: float
    coherence: float
    phase_spread: float
    buffer_margin: float
    persistence: int

    # Optional observational fields
    drift: Optional[float] = None
    afterglow: Optional[float] = None


# ---------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------

def load_dark_field(
    path: Path,
) -> Iterator[DarkFieldWaveView]:
    """
    Read a Dark Field JSONL file and yield WaveView projections.

    Rules:
    - Read-only
    - No directory creation
    - No mutation
    - Silent on missing file
    """

    if not path.exists():
        return iter(())

    def _iter() -> Iterator[DarkFieldWaveView]:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                record = json.loads(line)

                yield DarkFieldWaveView(
                    t=_parse_timestamp(record),
                    coherence=float(record.get("coherence", 0.0)),
                    phase_spread=float(record.get("phase", 0.0)),
                    buffer_margin=_buffer_margin(record),
                    persistence=_persistence(record),
                    drift=record.get("drift"),
                    afterglow=record.get("afterglow"),
                )

    return _iter()


# ---------------------------------------------------------------------
# Helpers (presentation-safe only)
# ---------------------------------------------------------------------

def _parse_timestamp(record: dict) -> float:
    """
    Extract timestamp as float seconds.
    Presentation convenience only.
    """
    ts = record.get("timestamp")
    if isinstance(ts, str):
        # ISO-8601 → epoch seconds
        from datetime import datetime
        return datetime.fromisoformat(ts).timestamp()
    return 0.0


def _buffer_margin(record: dict) -> float:
    """
    Best-effort buffer margin derivation.
    Defaults to full margin if unknown.
    """
    return float(record.get("buffer_margin", 1.0))


def _persistence(record: dict) -> int:
    """
    Best-effort persistence value.
    """
    return int(record.get("persistence", 1))
