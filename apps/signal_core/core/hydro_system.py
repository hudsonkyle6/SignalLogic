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
# Utilities
# ──────────────────────────────────────────────────────────────

def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def safe_relpath(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)

def norm_slashes(s: str) -> str:
    return s.replace("\\", "/")

def is_subpath(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────
# Repo Rules
# ──────────────────────────────────────────────────────────────

DEFAULT_IGNORE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "env", "dist", "build",
}

DEFAULT_IGNORE_GLOBS = [
    "*.pyc", "*.pyo", "*.tmp", "*.bak", "*.swp", "*.log",
]

# Absolute never-touch zones
NEVER_TOUCH_PREFIXES = [
    "archive/",
    "signal_light_press/archive/",
    "rhythm_os/data/",
]

# Safe bucket rules
SAFE_BUCKETS = [
    ("*.md", "docs"),
    ("*.txt", "docs"),
    ("*.json", "config"),
    ("*.yaml", "config"),
    ("*.yml", "config"),
    ("*.toml", "config"),
    ("*.ini", "config"),
    ("*.sh", "tools/scripts"),
    ("*.ps1", "tools/scripts"),
]

JUNK_DIR_NAMES = {"tmp", "temp", "old", "misc", "draft", "_old", "_tmp"}

# ──────────────────────────────────────────────────────────────
# Guards
# ──────────────────────────────────────────────────────────────

def should_ignore_path(p: Path) -> bool:
    for d in DEFAULT_IGNORE_DIRS:
        if d in p.parts:
            return True
    for g in DEFAULT_IGNORE_GLOBS:
        if fnmatch.fnmatch(p.name, g):
            return True
    return False

def is_never_touch(p: Path, root: Path) -> bool:
    rel = norm_slashes(safe_relpath(p, root)).lower()
    return any(rel.startswith(x) for x in NEVER_TOUCH_PREFIXES)

def is_python_package_dir(d: Path) -> bool:
    return (d / "__init__.py").exists()

def is_in_python_package(p: Path, root: Path) -> bool:
    cur = p.parent.resolve()
    root = root.resolve()
    while cur != root:
        if is_python_package_dir(cur):
            return True
        cur = cur.parent
    return False

# ──────────────────────────────────────────────────────────────
# Planning Structures
# ──────────────────────────────────────────────────────────────

@dataclasses.dataclass
class MoveOp:
    op: str               # "mkdir" | "move"
    src: Optional[str]
    dst: Optional[str]
    reason: str

@dataclasses.dataclass
class LayoutPlan:
    root: str
    created_at: str
    notes: List[str]
    ops: List[MoveOp]

def _unique_dst(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suf = dst.stem, dst.suffix
    for i in range(2, 1000):
        alt = dst.with_name(f"{stem}_{i}{suf}")
        if not alt.exists():
            return alt
    return dst

def _bucket_for_file(name: str) -> Optional[str]:
    lname = name.lower()
    for pat, bucket in SAFE_BUCKETS:
        if fnmatch.fnmatch(lname, pat):
            return bucket
    return None

# ──────────────────────────────────────────────────────────────
# Deep Layout Planner (Path-Preserving)
# ──────────────────────────────────────────────────────────────

def propose_layout_plan(root: Path, deep: bool = False) -> LayoutPlan:
    root = root.resolve()
    notes: List[str] = []
    ops: List[MoveOp] = []
    mkdirs: set[str] = set()

    candidates: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)

        dirnames[:] = [n for n in dirnames if n not in DEFAULT_IGNORE_DIRS]

        rel_dir = norm_slashes(safe_relpath(d, root))
        if is_never_touch(d, root):
            dirnames[:] = []
            continue

        for fn in filenames:
            p = d / fn
            if should_ignore_path(p) or is_never_touch(p, root):
                continue
            candidates.append(p)

    deep_moves = 0

    for p in sorted(candidates):
        if p.parent == root:
            continue

        dest_root = _bucket_for_file(p.name)
        if not dest_root:
            continue

        # Exclusions
        if "oracle/contracts" in norm_slashes(safe_relpath(p, root)).lower():
            continue
        if "boundary" in p.name.lower():
            continue

        rel_parent = norm_slashes(safe_relpath(p.parent, root)).lstrip("./")
        bucketed_rel = f"{dest_root}/{rel_parent}" if rel_parent else dest_root

        # README rule: never promote to docs root
        if p.name.lower() == "readme.md" and bucketed_rel.rstrip("/") == "docs":
            continue

        # Python rule: only loose scripts in junk
        if p.suffix == ".py":
            parts = set(rel_parent.lower().split("/"))
            if not (parts & JUNK_DIR_NAMES) or is_in_python_package(p, root):
                continue
            bucketed_rel = f"tools/loose_scripts/{rel_parent}"

        dst = _unique_dst(root / bucketed_rel / p.name)

        if dst.exists():
            notes.append(f"SKIP exists: {safe_relpath(p, root)} → {safe_relpath(dst, root)}")
            continue

        mkdirs.add(bucketed_rel)
        ops.append(MoveOp(
            "move",
            str(p),
            str(dst),
            f"Path-preserving bucket: {safe_relpath(p, root)} → {bucketed_rel}/"
        ))
        deep_moves += 1
        if deep_moves >= 3000:
            notes.append("STOP: deep move cap reached")
            break

    for d in sorted(mkdirs):
        ops.insert(0, MoveOp("mkdir", None, str(root / d), "Create bucket dir"))

    if not ops:
        notes.append("No safe moves proposed.")
    else:
        notes.append("Deep plan rules enforced (path-preserving, README-safe).")

    return LayoutPlan(
        root=str(root),
        created_at=now_ts(),
        notes=notes,
        ops=ops,
    )

# ──────────────────────────────────────────────────────────────
# Plan IO + Apply
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
        root=obj["root"],
        created_at=obj["created_at"],
        notes=obj["notes"],
        ops=[MoveOp(**op) for op in obj["ops"]],
    )

def apply_plan(plan: LayoutPlan) -> str:
    root = Path(plan.root).resolve()
    for op in plan.ops:
        if op.op == "mkdir":
            d = Path(op.dst)
            if not is_subpath(d, root):
                return f"Refused mkdir outside root: {d}"
            d.mkdir(parents=True, exist_ok=True)
        elif op.op == "move":
            src = Path(op.src)
            dst = Path(op.dst)
            if not src.exists():
                return f"Missing src: {src}"
            if dst.exists():
                return f"overwrite refused: {dst}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    return "Plan applied"

# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--propose-layout", action="store_true")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--save-plan", default="deep_plan.json")
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
        print(apply_plan(plan))
        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
