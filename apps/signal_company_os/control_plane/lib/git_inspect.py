from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

def run_git(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(["git", *cmd], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        return f"[GIT ERROR] git {' '.join(cmd)}\n{p.stderr.strip()}"
    return p.stdout.strip()

def inspect_git(repo_root: Path, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "repo": str(repo_root),
        "branch": run_git(["branch", "--show-current"], repo_root),
        "status_porcelain": run_git(["status", "--porcelain=v1"], repo_root),
        "status_short": run_git(["status", "-sb"], repo_root),
        "diff_stat": run_git(["diff", "--stat"], repo_root),
        "diff_name_status": run_git(["diff", "--name-status"], repo_root),
        "diff_check": run_git(["diff", "--check"], repo_root),
        "untracked": run_git(["ls-files", "--others", "--exclude-standard"], repo_root),
        "rename_detect": run_git(["diff", "--find-renames", "--name-status"], repo_root),
    }

    (out_dir / "git_report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    md = []
    md.append("# Git Ledger Report")
    md.append("")
    md.append(f"- Repo: `{data['repo']}`")
    md.append(f"- Branch: `{data['branch']}`")
    md.append("")
    md.append("## Status")
    md.append("```")
    md.append(data["status_short"] or "(clean)")
    md.append("```")
    md.append("")
    md.append("## Diff Stat")
    md.append("```")
    md.append(data["diff_stat"] or "(no diff)")
    md.append("```")
    md.append("")
    md.append("## Name/Status")
    md.append("```")
    md.append(data["diff_name_status"] or "(none)")
    md.append("```")
    md.append("")
    md.append("## Untracked")
    md.append("```")
    md.append(data["untracked"] or "(none)")
    md.append("```")
    md.append("")
    md.append("## Whitespace/CRLF Checks")
    md.append("```")
    md.append(data["diff_check"] or "(none)")
    md.append("```")
    (out_dir / "git_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return data
