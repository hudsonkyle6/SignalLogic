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
from datetime import datetime, timezone, date
from typing import Optional

from rhythm_os.core.wave.wave import Wave
from rhythm_os.runtime.paths import DATA_DIR
from signal_core.core.log import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------
# PATHS (definition only — no side effects here)
# ---------------------------------------------------------------------

DARK_FIELD_DIR = DATA_DIR / "dark_field"
PENSTOCK_DIR = DARK_FIELD_DIR / "penstock"


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _daily_file(anchor_date: date) -> Path:
    """
    Resolve the daily Penstock file path for a given date.
    """
    return PENSTOCK_DIR / f"{anchor_date.isoformat()}.jsonl"


# ---------------------------------------------------------------------
# APPEND-ONLY WRITE (activation boundary)
# ---------------------------------------------------------------------

def append_wave_from_hydro(
    wave: Wave,
    *,
    anchor_date: Optional[date] = None
) -> Path:
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

    # -------------------------------------------------------------
    # Resolve anchor date from Wave timestamp
    # -------------------------------------------------------------
    if anchor_date is None:
        try:
            ts = datetime.fromisoformat(wave.timestamp)
        except Exception:
            ts = datetime.now(timezone.utc)

        anchor_date = ts.date()

    # -------------------------------------------------------------
    # Resolve output path
    # -------------------------------------------------------------
    path = _daily_file(anchor_date)

    # Lazy bootstrap — lawful append boundary
    path.parent.mkdir(parents=True, exist_ok=True)

    log.debug("penstock write path=%s", path.resolve())

    # -------------------------------------------------------------
    # Append-only write
    # -------------------------------------------------------------
    record = wave.to_json()

    with path.open("a", encoding="utf-8") as f:
        f.write(record)
        f.write("\n")

    return path
