from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ALLOWED_OPS = {"mkdir", "move"}

@dataclass
class Plan:
    root: Path
    created_at: str
    policy: Dict[str, Any]
    notes: List[str]
    ops: List[Dict[str, Any]]

def validate_plan_obj(obj: Dict[str, Any]) -> Plan:
    if "root" not in obj or "ops" not in obj:
        raise ValueError("Invalid plan: missing root/ops")

    root = Path(obj["root"])
    ops = obj.get("ops", [])
    if not isinstance(ops, list):
        raise ValueError("Invalid plan: ops must be list")

    for i, op in enumerate(ops):
        if op.get("op") not in ALLOWED_OPS:
            raise ValueError(f"Invalid op[{i}]: op must be one of {sorted(ALLOWED_OPS)}")
        if op["op"] == "mkdir":
            if not op.get("dst"):
                raise ValueError(f"Invalid mkdir[{i}]: missing dst")
        if op["op"] == "move":
            if not op.get("src") or not op.get("dst"):
                raise ValueError(f"Invalid move[{i}]: missing src/dst")
        if not op.get("reason"):
            raise ValueError(f"Invalid op[{i}]: missing reason")

    return Plan(
        root=root,
        created_at=str(obj.get("created_at", "")),
        policy=dict(obj.get("policy", {})),
        notes=list(obj.get("notes", [])),
        ops=ops
    )
