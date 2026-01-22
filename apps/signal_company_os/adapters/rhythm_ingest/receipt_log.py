"""
RHYTHM_OS Envelope Receipt Log — APPEND ONLY

This module records the receipt of RHYTHM_OS envelopes.
It does not interpret, aggregate, or act.

Rules:
- Append-only NDJSON
- No edits or deletes
- No thresholds
- No authority
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import json


def append_receipt(
    *,
    envelope_id: str,
    shepherd_posture: str,
    source_path: Path,
    log_dir: Path,
) -> None:
    """
    Append a single receipt record for an ingested envelope.

    This records:
    - when the envelope was received
    - which envelope it was
    - the posture at time of receipt
    - the source file path

    No interpretation is performed.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "envelope_receipts.ndjson"

    record: Dict[str, Any] = {
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "envelope_id": envelope_id,
        "shepherd_posture": shepherd_posture,
        "source_path": str(source_path),
    }

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
