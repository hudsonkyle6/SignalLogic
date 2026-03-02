from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .policy import Policy
from .plan_schema import validate_plan_obj
from .executor import apply_ops
from .gate_ledger import append_gate


def _get_repo_root(policy: Policy, root_override: Optional[str]) -> Path:
    return Path(root_override) if root_override else policy.production_root


def _get_apply_root(policy: Policy, mode: str) -> Path:
    return policy.production_root if mode == "production" else policy.lab_root


def run_apply(
    policy: Policy, plan_path: Path, mode: str, root_override: Optional[str] = None
) -> int:
    repo_root = _get_repo_root(policy, root_override)
    apply_root = _get_apply_root(policy, mode)

    obj = json.loads(plan_path.read_text(encoding="utf-8"))
    plan = validate_plan_obj(obj)

    # Root match rule: plan.root must equal apply_root
    if str(plan.root) != str(apply_root):
        raise SystemExit(
            f"Refusing apply: plan.root={plan.root} != apply_root={apply_root}"
        )

    if policy.require_gate_for_apply:
        print("\n[GATE WARDEN] → Human required")
        print("  Purpose : Apply plan")
        print(f"  Scope   : plan={plan_path} ops={len(plan.ops)} root={apply_root}")
        sig = input("Enter signature (name/time) or 'deny': ").strip()
        if sig.lower() in ("deny", "n", "no"):
            print("Gate denied → apply terminated.")
            return 2
        append_gate(
            policy.gate_ledger_path,
            purpose="Apply plan",
            scope=f"{plan_path} ops={len(plan.ops)}",
            signature=sig,
        )

    logs = apply_ops(
        plan_root=apply_root,
        repo_root=repo_root,
        never_touch=policy.never_touch,
        ops=plan.ops,
    )
    for ln in logs:
        print(ln)
    print("APPLY COMPLETE")
    return 0
