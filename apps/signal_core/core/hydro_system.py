# hydro_system.py
# Run-of-River "Hydro" Multi-Agent System
# Repo comb + safe layout optimization (shallow / deep)

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import json
import os
import re
import shutil
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def norm_slashes(s: str) -> str:
    return s.replace("\\", "/")

def safe_relpath(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)

def is_subpath(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────
# Boundary / Doctrine Guard (authoritative)
# ──────────────────────────────────────────────────────────────
def is_never_move_file(p: Path) -> bool:
    """
    Boundary / doctrine files must never move.
    Semantic rule: any filename containing 'BOUNDARY' is protected.
    """
    return "BOUNDARY" in p.name.upper()

# ──────────────────────────────────────────────────────────────
# Ignore / safety rules
# ──────────────────────────────────────────────────────────────
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "env",
    "dist", "build", ".idea", ".vscode",
}

DEFAULT_IGNORE_GLOBS = [
    "*.pyc", "*.pyo", "*.pyd", "*.tmp", "*.bak", "*.swp",
    "*.log", "*.sqlite", "*.db",
]

# These paths are NEVER inspected or moved
DEFAULT_NEVER_TOUCH_PREFIXES = [
    "signal_light_press/archive/",
    "signal_light_press/_quarantine/",
    "archive/",
    "rhythm_os/data/",
]

SAFE_DEEP_BUCKETS = [
    ("*.md", "docs"),
    ("*.txt", "docs"),
    ("*.pdf", "docs"),
    ("*.rst", "docs"),
    ("*.yml", "config"),
    ("*.yaml", "config"),
    ("*.json", "config"),
    ("*.toml", "config"),
    ("*.ini", "config"),
    ("*.ipynb", "research/notebooks"),
    ("*.ps1", "tools/scripts"),
    ("*.bat", "tools/scripts"),
    ("*.sh", "tools/scripts"),
    ("*.png", "assets/images"),
    ("*.jpg", "assets/images"),
    ("*.jpeg", "assets/images"),
    ("*.webp", "assets/images"),
    ("*.svg", "assets/images"),
]

JUNK_DIR_NAMES = {
    "tmp", "temp", "old", "misc", "scratch",
    "draft", "dead", "deprecated", "_old", "_tmp"
}

# ──────────────────────────────────────────────────────────────
# Utility checks
# ──────────────────────────────────────────────────────────────
def should_ignore_path(p: Path) -> bool:
    parts = {x.name for x in p.parents} | {p.name}
    if any(d in parts for d in DEFAULT_IGNORE_DIRS):
        return True
    for g in DEFAULT_IGNORE_GLOBS:
        if fnmatch.fnmatch(p.name, g):
            return True
    return False

def is_never_touch(p: Path, root: Path) -> bool:
    rel = norm_slashes(safe_relpath(p, root)).lower()
    return any(rel.startswith(prefix) for prefix in DEFAULT_NEVER_TOUCH_PREFIXES)

def _unique_dst(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suf = dst.stem, dst.suffix
    parent = dst.parent
    for i in range(2, 1000):
        cand = parent / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
    return dst

def _bucket_for_file(name: str, buckets: List[Tuple[str, str]]) -> Optional[str]:
    lname = name.lower()
    for pat, dst in buckets:
        if fnmatch.fnmatch(lname, pat.lower()):
            return dst
    return None

# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────
@dataclasses.dataclass
class MoveOp:
    op: str  # mkdir | move
    src: Optional[str] = None
    dst: Optional[str] = None
    reason: str = ""

@dataclasses.dataclass
class LayoutPlan:
    root: str
    created_at: str
    notes: List[str]
    ops: List[MoveOp]

# ──────────────────────────────────────────────────────────────
# Layout planner
# ──────────────────────────────────────────────────────────────
def propose_layout_plan(root: Path, deep: bool) -> LayoutPlan:
    root = root.resolve()
    ops: List[MoveOp] = []
    notes: List[str] = []
    mkdirs = set()
    candidates: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if n not in DEFAULT_IGNORE_DIRS]

        rel_dir = norm_slashes(safe_relpath(d, root))
        if any(rel_dir.lower().startswith(pfx) for pfx in DEFAULT_NEVER_TOUCH_PREFIXES):
            dirnames[:] = []
            continue

        for fn in filenames:
            p = d / fn
            if should_ignore_path(p):
                continue
            if is_never_touch(p, root):
                continue
            if is_never_move_file(p):
                continue
            candidates.append(p)

    # Root-level bucketing
    for p in sorted([c for c in candidates if c.parent == root]):
        dest_dir = _bucket_for_file(p.name, SAFE_DEEP_BUCKETS)
        if not dest_dir:
            continue
        dst = _unique_dst(root / dest_dir / p.name)
        mkdirs.add(dest_dir)
        ops.append(MoveOp("move", str(p), str(dst), "Bucket root file"))

    if deep:
        for p in sorted([c for c in candidates if c.parent != root]):
            if is_never_move_file(p):
                continue
            dest_dir = _bucket_for_file(p.name, SAFE_DEEP_BUCKETS)
            if not dest_dir:
                continue
            dst = _unique_dst(root / dest_dir / p.name)
            mkdirs.add(dest_dir)
            ops.append(MoveOp(
                "move",
                str(p),
                str(dst),
                f"Deep bucket: {safe_relpath(p, root)} → {dest_dir}/"
            ))

    for drel in sorted(mkdirs):
        dpath = (root / drel)
        if not dpath.exists():
            ops.insert(0, MoveOp("mkdir", None, str(dpath), "Create bucket"))

    notes.append("Boundary / doctrine files exempt")
    notes.append("signal_light_press quarantine exempt")
    notes.append("No deletes, no overwrites")

    return LayoutPlan(str(root), now_ts(), notes, ops)

# ──────────────────────────────────────────────────────────────
# Plan persistence
# ──────────────────────────────────────────────────────────────
def save_plan(plan: LayoutPlan, out_path: Path) -> None:
    out_path.write_text(json.dumps({
        "root": plan.root,
        "created_at": plan.created_at,
        "notes": plan.notes,
        "ops": [dataclasses.asdict(op) for op in plan.ops],
    }, indent=2), encoding="utf-8")

def load_plan(path: Path) -> LayoutPlan:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return LayoutPlan(
        obj["root"],
        obj["created_at"],
        obj.get("notes", []),
        [MoveOp(**op) for op in obj.get("ops", [])],
    )

def apply_plan(plan: LayoutPlan) -> Tuple[bool, str]:
    root = Path(plan.root).resolve()
    for op in plan.ops:
        if op.op == "mkdir":
            dst = Path(op.dst).resolve()
            if not is_subpath(dst, root):
                return False, "mkdir outside root refused"
            dst.mkdir(parents=True, exist_ok=True)
        elif op.op == "move":
            src = Path(op.src).resolve()
            dst = Path(op.dst).resolve()
            if not is_subpath(src, root) or not is_subpath(dst, root):
                return False, "move outside root refused"
            if dst.exists():
                return False, f"overwrite refused: {dst}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    return True, "Plan applied"

# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--propose-layout", action="store_true")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--save-plan", default="layout_plan.json")
    ap.add_argument("--apply-plan")
    args = ap.parse_args()

    root = Path(args.root)

    if args.propose_layout:
        plan = propose_layout_plan(root, deep=args.deep)
        save_plan(plan, Path(args.save_plan))
        print(json.dumps({
            "ops": len(plan.ops),
            "notes": plan.notes,
        }, indent=2))
        return 0

    if args.apply_plan:
        plan = load_plan(Path(args.apply_plan))
        ok, msg = apply_plan(plan)
        print(msg)
        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
