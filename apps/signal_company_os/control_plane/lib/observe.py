from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .policy import Policy
from .doctrine import compile_slp
from .git_inspect import inspect_git

def _get_root(policy: Policy, mode: str, root_override: Optional[str]) -> Path:
    if root_override:
        return Path(root_override)
    return policy.production_root if mode == "production" else policy.lab_root

def run_observe(policy: Policy, out_dir: Path, mode: str, root_override: Optional[str] = None) -> int:
    repo_root = _get_root(policy, mode="production", root_override=root_override)  # repo root always production
    slp_root = repo_root / policy.slp_root

    out_dir.mkdir(parents=True, exist_ok=True)

    doctrine = compile_slp(
        slp_root=slp_root,
        suffixes=policy.slp_suffixes,
        required_keys=policy.slp_required_keys,
        out_dir=out_dir
    )
    git = inspect_git(repo_root=repo_root, out_dir=out_dir)

    summary = {
        "mode": mode,
        "repo_root": str(repo_root),
        "slp_root": str(slp_root),
        "doctrine_counts": doctrine["counts"],
        "git_branch": git["branch"],
        "dirty": bool(git["status_porcelain"].strip()),
    }
    (out_dir / "observe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"WROTE: {out_dir / 'observe_summary.json'}")
    print(f"WROTE: {out_dir / 'doctrine_report.md'}")
    print(f"WROTE: {out_dir / 'git_report.md'}")
    return 0
