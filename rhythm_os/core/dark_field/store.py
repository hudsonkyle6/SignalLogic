# rhythm_os/core/dark_field/store.py

"""
DARK FIELD — Append-Only Wave Archive

Role:
- Immutable memory
- Non-actionable observation store
- Coherence substrate (read-only for others)

Governance:
- Assist Under Discipline
- No evaluation
- No mutation
- No authority

DOCTRINE — ECOTONE BOOTSTRAP RULE
- Persistence edges bootstrap lazily on first lawful use.
- No eager filesystem creation at import / definition time.
- Silence (absence of structure) is recoverable.
- Side effects occur only as a byproduct of append, never on import.

This module ONLY appends sealed Waves.
"""

from __future__ import annotations

from pathlib import Path
from datetime import date
from typing import Optional

from rhythm_os.core.wave.wave import Wave


# ---------------------------------------------------------------------
# PATHS (definition only — no side effects here)
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]  # SignalLogic/
DARK_FIELD_DIR = ROOT / "data" / "dark_field"


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _daily_file(anchor_date: date) -> Path:
    """
    Resolve the daily Dark Field file path for a given date.
    No filesystem mutation occurs here.
    """
    return DARK_FIELD_DIR / f"{anchor_date.isoformat()}.jsonl"


# ---------------------------------------------------------------------
# APPEND-ONLY WRITE (activation boundary)
# ---------------------------------------------------------------------

def append_wave(wave: Wave, *, anchor_date: Optional[date] = None) -> Path:
    """
    Append a sealed Wave to the Dark Field.

    Rules:
    - Append-only
    - One Wave per line (JSONL)
    - No overwrite
    - No read-back

    Ecotone behavior:
    - Directory structure bootstraps lazily on first append.
    """

    if anchor_date is None:
        anchor_date = wave.timestamp.date()

    path = _daily_file(anchor_date)

    # Lazy bootstrap — side effect occurs only on lawful append
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize once, exactly (authority remains with Wave)
    record = wave.to_json()

    with path.open("a", encoding="utf-8") as f:
        f.write(record)
        f.write("\n")

    return path
