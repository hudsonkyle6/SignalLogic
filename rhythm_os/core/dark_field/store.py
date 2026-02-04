# rhythm_os/core/dark_field/store.py

"""
IMMUTABLE DARK FIELD STORE

This module is Hydro-owned.

Rules:
- May only be called by Hydro Basin 1
- All Waves must have passed the Hydro Ingress Gate
- Observatory and extractors must never call this directly

If this module is imported outside Hydro, that is a violation.
"""


from __future__ import annotations

from pathlib import Path
from datetime import datetime,timezone
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

def append_wave_from_hydro(wave: Wave, *, anchor_date: Optional[date] = None) -> Path:
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
        try:
            # Wave.timestamp is ISO-8601 string by contract
            ts = datetime.fromisoformat(wave.timestamp)
        except Exception:
            # Absolute fallback — should never happen, but stays safe
            ts = datetime.now(timezone.utc)

        anchor_date = ts.date()

    
        

    path = _daily_file(anchor_date)

    # Lazy bootstrap — side effect occurs only on lawful append
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize once, exactly (authority remains with Wave)
    record = wave.to_json()

    with path.open("a", encoding="utf-8") as f:
        f.write(record)
        f.write("\n")

    return path
