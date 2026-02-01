from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Tuple

def _norm_glob(p: Path) -> str:
    return str(p.as_posix())

def _matches_any_glob(path: Path, globs: List[str]) -> bool:
    s = _norm_glob(path)
    for g in globs:
        # normalize patterns to posix-like
        gp = g.replace("\\", "/")
        if fnmatch.fnmatch(s, gp):
            return True
    return False

def _assert_under_root(root: Path, target: Path):
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise RuntimeError(f"Refusing operation outside root: {target}")

def _assert_not_never_touch(repo_root: Path, target: Path, never_touch: List[str]):
    # match against repo-relative posix
    repo_root = repo_root.resolve()
    target = target.resolve()
    try:
        rel = target.relative_to(repo_root)
    except ValueError:
        # if outside repo root, block earlier anyway
        rel = target
    if _matches_any_glob(rel, never_touch):
        raise RuntimeError(f"Refusing touch (never_touch): {rel}")

def apply_ops(plan_root: Path, repo_root: Path, never_touch: List[str], ops: List[Dict[str, Any]]) -> List[str]:
    """
    Apply mkdir/move with:
    - no overwrites
    - no deletes
    - must be inside plan_root
    - must not match never_touch (repo-relative)
    """
    logs: List[str] = []
    for op in ops:
        kind = op["op"]
        if kind == "mkdir":
            dst = Path(op["dst"])
            _assert_under_root(plan_root, dst)
            _assert_not_never_touch(repo_root, dst, never_touch)
            if dst.exists():
                logs.append(f"SKIP mkdir (exists): {dst}")
            else:
                dst.mkdir(parents=True, exist_ok=False)
                logs.append(f"OK mkdir: {dst}")

        elif kind == "move":
            src = Path(op["src"])
            dst = Path(op["dst"])
            _assert_under_root(plan_root, src)
            _assert_under_root(plan_root, dst)
            _assert_not_never_touch(repo_root, src, never_touch)
            _assert_not_never_touch(repo_root, dst, never_touch)

            if not src.exists():
                logs.append(f"SKIP move (missing src): {src}")
                continue
            if dst.exists():
                raise RuntimeError(f"Refusing overwrite (dst exists): {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)  # atomic rename/move on same volume
            logs.append(f"OK move: {src} -> {dst}")
        else:
            raise RuntimeError(f"Unsupported op: {kind}")
    return logs
