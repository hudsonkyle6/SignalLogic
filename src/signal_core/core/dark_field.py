#dark_field.py
"""
POSTURE: PENSTOCK
Immutable, append-only history.
Must only be written via Hydro.

See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations



import json
import hashlib
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from .hydro_types import HydroPacket

# Allowed record types (Hydro boundary)
RECORD_INGRESS = "ingress_record"
RECORD_DISPATCH = "dispatch_record"
RECORD_LIGHTHOUSE = "lighthouse_summary"
RECORD_HUMAN = "human_signature"

INGRESS_PATH = Path("src/rhythm_os/data/dark_field/hydro/ingress.jsonl")
def append_hydro_ingress_packet(packet: HydroPacket) -> None:
    INGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INGRESS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet.__dict__, ensure_ascii=False) + "\n")

def _utc_date_from_t(t: float) -> str:
    return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d")


def _canonical_json(obj: Dict[str, Any]) -> str:
    # Deterministic serialization for hashing
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_integrity_hash(record_wo_hash: Dict[str, Any]) -> str:
    """
    SHA-256 over canonical JSON of the record without integrity_hash field.
    """
    payload = _canonical_json(record_wo_hash).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add integrity_hash deterministically.
    """
    if "integrity_hash" in record:
        raise ValueError("record already contains integrity_hash")

    h = compute_integrity_hash(record)
    sealed = dict(record)
    sealed["integrity_hash"] = h
    return sealed


def append_record(
    record: Dict[str, Any],
    *,
    base_dir: Path,
    filename_date: Optional[str] = None,
) -> Path:
    """
    Append-only JSONL writer.

    - Creates directories if missing
    - Never overwrites, only appends
    - Returns the path written to
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Determine date-based file name
    if filename_date is None:
        if "t" not in record:
            raise ValueError("record missing 't' timestamp")
        filename_date = _utc_date_from_t(float(record["t"]))

    path = base_dir / f"{filename_date}.jsonl"

    sealed = seal_record(record)

    line = _canonical_json(sealed) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)

    return path


def _as_value(x: Any) -> Any:
    if is_dataclass(x):
        return asdict(x)
    return x
