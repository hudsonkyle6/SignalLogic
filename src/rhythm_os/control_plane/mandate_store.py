from __future__ import annotations

from pathlib import Path
from typing import Optional
import json

from .mandate import Mandate, MandateError, validate_mandate_dict


def load_latest_mandate(mandates_dir: Path) -> Optional[Mandate]:
    """
    Loads the newest mandate file by modified time.
    Mandates are expected to be stored as JSON files, append-only by convention.

    This is read-only and does not enforce any directory creation.
    """
    if not mandates_dir.exists() or not mandates_dir.is_dir():
        return None

    candidates = sorted(
        mandates_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        return None

    p = candidates[0]
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MandateError("mandate file must contain a JSON object")

    validate_mandate_dict(data)
    return Mandate.from_dict(data)
