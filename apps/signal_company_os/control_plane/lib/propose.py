from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from .policy import Policy

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def _get_repo_root(policy: Policy, root_override: Optional[str]) -> Path:
    return Path(root_override) if root_override else policy.production_root

def run_propose(policy: Policy, out_dir: Path, mode: str, root_override: Optional[str], scope: str) -> int:
    """
    v0 proposes only a "worklist plan" (no moves) based on doctrine+git signals.
    This is intentional: first proposals should be inert.
    """
    repo_root = _get_repo_root(policy, root_override)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Inert plan: ops empty; worklist populated.
    worklist: List[Dict[str, Any]] = []
    if "slp" in scope:
        worklist.append({
            "tier": "P0",
            "item": "Review doctrine_report.md missing headers and resolve (no auto-edits).",
            "risk": "low",
            "reversible": True
        })
    if "git" in scope:
        worklist.append({
            "tier": "P0",
            "item": "Review git_report.md; ensure no unintended changes before applying any plans.",
            "risk": "low",
            "reversible": True
        })

    plan = {
        "root": str(repo_root if mode == "production" else policy.lab_root),
        "created_at": _now(),
        "policy": {
            "scope": mode,
            "never_touch": policy.never_touch,
            "overwrite": False,
            "deletes": False
        },
        "notes": [
            "v0 proposal is inert (no ops). It only produces a signed worklist and reports.",
            "Next: add real planners (layout, doctrine reconciliation, promotion gates)."
        ],
        "worklist": worklist,
        "ops": []
    }

    plan_path = out_dir / f"proposal_{mode}_{int(time.time())}.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"WROTE: {plan_path}")
    return 0
