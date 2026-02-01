# ✅ Going deeper (without breaking the world)
# Principle: deep re-layout is allowed, but only where it’s mechanically safe:
# - docs/config/scripts/notebooks/assets can move across the tree
# - code moves are restricted to "loose" scripts (not packages) and “junk zones”
# - archives + data stores are never touched
#
# This update adds:
#   --deep                 (enables deeper proposals)
#   --policy policy.json   (optional override / tuning)
#   deep-aware plan rules  (safe buckets + junk consolidation)
#
# Drop-in replacement script below.

#cat > hydro_system.py << 'EOF'
# hydro_system.py
# Run-of-River "Hydro" Multi-Agent System with:
# - Truth Logic Gates (LLM proposes FACTS; Python resolves truth state deterministically)
# - Human-signed gates for execution / structural changes
# - System-generated Work List
# - Repo comb + layout optimization proposals (shallow OR deep)
#
# Requirements:
#   pip install requests
#   Ollama running locally (optional but recommended)
#
# Usage:
#   python hydro_system.py --interactive
#   python hydro_system.py --root "C:\Users\SignalADmin\Signal Archive\SignalLogic" --scan
#   python hydro_system.py --root "C:\Users\SignalADmin\Signal Archive\SignalLogic" --propose-layout
#   python hydro_system.py --root "C:\Users\SignalADmin\Signal Archive\SignalLogic" --propose-layout --deep
#   python hydro_system.py --root "C:\Users\SignalADmin\Signal Archive\SignalLogic" --propose-layout --deep --save-plan deep_plan.json
#   python hydro_system.py --root "C:\Users\SignalADmin\Signal Archive\SignalLogic" --service-mode --apply-plan deep_plan.json
#
# Safety posture:
# - NEVER deletes.
# - NEVER overwrites.
# - Applies changes ONLY in SERVICE mode + human signature.
# - Deep mode still refuses risky code moves (packages/imported modules).
#
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

import requests

# ──────────────────────────────────────────────────────────────
# Ollama config (optional)
# ──────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
PRIMARY_MODEL = "llama3.1:8b"
LIGHT_MODEL = "mistral:latest"

TRUTH_STATES = [
    "OBSERVE_ONLY", "PROPOSE_ALLOWED", "ACTION_ELIGIBLE",
    "SERVICE_ONLY", "BLOCKED", "EMERGENCY_WATCH"
]
SYSTEM_MODES = ["RUN", "INSPECT", "SERVICE", "ARCHIVE"]

# ──────────────────────────────────────────────────────────────
# Helpers
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

def is_subpath(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False

def norm_slashes(s: str) -> str:
    return s.replace("\\", "/")

# ──────────────────────────────────────────────────────────────
# HydroAgent
# ──────────────────────────────────────────────────────────────
class HydroAgent:
    def __init__(self, name: str, system_prompt: str, model: str = PRIMARY_MODEL):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.memory = deque(maxlen=8)

    def think(self, user_message: str, temperature: float = 0.45) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.memory,
            {"role": "user", "content": user_message},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature, "num_ctx": 8192},
            "stream": False,
        }
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=90)
            r.raise_for_status()
            content = r.json()["message"]["content"].strip()
            self.memory.append({"role": "user", "content": user_message})
            self.memory.append({"role": "assistant", "content": content})
            return content
        except Exception as e:
            return f"[{self.name} ERROR] {e}"

# ──────────────────────────────────────────────────────────────
# Truth Logic Gates (digital)
# ──────────────────────────────────────────────────────────────
@dataclasses.dataclass
class TruthFacts:
    invariants_ok: bool = True
    pressure_high: bool = False
    overload: bool = False
    ambiguity: bool = False
    incoherent: bool = False
    maintenance_due: bool = False
    human_requested_action: bool = False
    service_window_only: bool = False
    conflict_detected: bool = False

def resolve_truth_state(f: TruthFacts, mode: str) -> str:
    if mode not in SYSTEM_MODES:
        return "BLOCKED"

    # inhibitors (NOT-gates)
    if f.overload:
        return "EMERGENCY_WATCH"
    if f.incoherent:
        return "BLOCKED"
    if f.ambiguity:
        return "OBSERVE_ONLY"
    if not f.invariants_ok:
        return "BLOCKED"
    if f.conflict_detected:
        return "EMERGENCY_WATCH"

    # service dominates
    if mode == "SERVICE" or f.service_window_only or f.maintenance_due:
        return "SERVICE_ONLY"

    # action eligibility requires concurrence (AND)
    if f.pressure_high and f.human_requested_action:
        return "ACTION_ELIGIBLE"

    return "PROPOSE_ALLOWED"

def parse_truth_facts_llm(text: str) -> Optional[TruthFacts]:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        f = TruthFacts()
        for k in dataclasses.asdict(f).keys():
            if k in obj and isinstance(obj[k], bool):
                setattr(f, k, obj[k])
        return f
    except Exception:
        return None

# ──────────────────────────────────────────────────────────────
# Repo scanning + Layout Optimization
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

# never touch these zones (conservative)
DEFAULT_NEVER_TOUCH_PREFIXES = [
    "signal_light_press/archive/",
    "archive/",
    "rhythm_os/data/",
]

# Buckets for safe file types (can be moved in deep mode)
SAFE_DEEP_BUCKETS = [
    # docs
    ("*.md", "docs"),
    ("*.txt", "docs"),
    ("*.pdf", "docs"),
    ("*.rst", "docs"),
    # config
    ("*.yml", "config"),
    ("*.yaml", "config"),
    ("*.json", "config"),
    ("*.toml", "config"),
    ("*.ini", "config"),
    # notebooks / research
    ("*.ipynb", "research/notebooks"),
    # scripts
    ("*.ps1", "tools/scripts"),
    ("*.bat", "tools/scripts"),
    ("*.sh", "tools/scripts"),
    # assets
    ("*.png", "assets/images"),
    ("*.jpg", "assets/images"),
    ("*.jpeg", "assets/images"),
    ("*.webp", "assets/images"),
    ("*.svg", "assets/images"),
]

# "junk zones": folders that often hold throwaway material
JUNK_DIR_NAMES = {"tmp", "temp", "old", "misc", "scratch", "draft", "dead", "deprecated", "_old", "_tmp"}

# Special handling: allow moving "loose scripts" only if NOT in a python package
# (i.e., not under any directory containing __init__.py)
def is_python_package_dir(d: Path) -> bool:
    return (d / "__init__.py").exists()

def is_in_python_package(p: Path, root: Path) -> bool:
    cur = p.parent
    root = root.resolve()
    while True:
        if cur == root:
            return False
        if is_python_package_dir(cur):
            return True
        if cur.parent == cur:
            return False
        cur = cur.parent

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

def scan_repo(root: Path, max_files: int = 200000) -> Dict[str, Any]:
    root = root.resolve()
    ext_counts = Counter()
    total_files = 0
    loose_root = []
    junk_dirs_found = Counter()

    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # prune ignored dirs
        dirnames[:] = [n for n in dirnames if n not in DEFAULT_IGNORE_DIRS]

        # track junk dirs (presence)
        for dn in dirnames:
            if dn.lower() in JUNK_DIR_NAMES:
                junk_dirs_found[dn.lower()] += 1

        for fn in filenames:
            p = d / fn
            total_files += 1
            if total_files > max_files:
                break
            if should_ignore_path(p) or is_never_touch(p, root):
                continue
            ext = p.suffix.lower() if p.suffix else "<none>"
            ext_counts[ext] += 1
            if p.parent == root:
                loose_root.append(p.name)

        if total_files > max_files:
            break

    warnings = []
    if len(loose_root) > 12:
        warnings.append(f"High root clutter: {len(loose_root)} files at root.")
    if sum(junk_dirs_found.values()) > 0:
        warnings.append(f"Junk zones detected: {dict(junk_dirs_found)}")

    return {
        "root": str(root),
        "top_extensions": ext_counts.most_common(20),
        "root_files": sorted(loose_root),
        "junk_dirs": dict(junk_dirs_found),
        "warnings": warnings,
    }

@dataclasses.dataclass
class MoveOp:
    op: str  # "mkdir" | "move"
    src: Optional[str] = None
    dst: Optional[str] = None
    reason: str = ""

@dataclasses.dataclass
class LayoutPlan:
    root: str
    created_at: str
    policy: Dict[str, Any]
    notes: List[str]
    ops: List[MoveOp]

def _unique_dst(dst: Path) -> Path:
    """
    Ensure we never overwrite; if exists, suffix with _N.
    """
    if not dst.exists():
        return dst
    stem = dst.stem
    suf = dst.suffix
    parent = dst.parent
    for i in range(2, 1000):
        cand = parent / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
    # last resort: just return original (will be refused later)
    return dst

def _bucket_for_file(name: str, buckets: List[Tuple[str, str]]) -> Optional[str]:
    lname = name.lower()
    for pat, dst in buckets:
        if fnmatch.fnmatch(lname, pat.lower()):
            return dst
    return None

def propose_layout_plan(root: Path, deep: bool = False, policy_path: Optional[str] = None) -> LayoutPlan:
    """
    SHALLOW (default):
      - bucket only root-level files into docs/config/tools/assets
    DEEP (safe):
      - also bucket SAFE file types found anywhere into centralized buckets
      - consolidate junk zones into ./_quarantine/<path> (move only non-code)
      - allow moving "loose scripts" (.py) ONLY if they are NOT in a python package
        AND are located in junk zones (tmp/misc/etc)
    """
    root = root.resolve()

    # Load optional policy overrides
    buckets = list(SAFE_DEEP_BUCKETS)
    junk_names = set(JUNK_DIR_NAMES)
    never_touch = list(DEFAULT_NEVER_TOUCH_PREFIXES)
    max_depth = 999 if deep else 1

    if policy_path:
        try:
            obj = json.loads(Path(policy_path).read_text(encoding="utf-8"))
            buckets = obj.get("buckets", buckets)
            junk_names = set(obj.get("junk_dir_names", list(junk_names)))
            never_touch = obj.get("never_touch_prefixes", never_touch)
            max_depth = int(obj.get("max_depth", max_depth))
        except Exception:
            pass

    policy = {
        "deep": deep,
        "max_depth": max_depth,
        "buckets": buckets,
        "junk_dir_names": sorted(junk_names),
        "never_touch_prefixes": never_touch,
        "rules": {
            "no_deletes": True,
            "no_overwrites": True,
            "deep_moves_allowed_for": "docs/config/notebooks/scripts/assets (safe types)",
            "python_code_moves": "only loose .py in junk zones AND not in python packages",
        },
    }

    notes: List[str] = []
    ops: List[MoveOp] = []
    mkdirs = set()

    # Helper: add mkdir once
    def ensure_dir(rel_dir: str):
        d = (root / rel_dir).resolve()
        if not is_subpath(d, root):
            return
        if not d.exists():
            mkdirs.add(rel_dir)

    # Collect candidates
    candidates: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # prune ignore
        dirnames[:] = [n for n in dirnames if n not in DEFAULT_IGNORE_DIRS]

        rel_dir = norm_slashes(safe_relpath(d, root))
        # never touch zones
        if any(rel_dir.lower().startswith(pfx) for pfx in never_touch):
            dirnames[:] = []
            continue

        # depth limit
        depth = 0 if rel_dir == "." else rel_dir.count("/") + 1
        if depth > max_depth:
            dirnames[:] = []
            continue

        for fn in filenames:
            p = d / fn
            if should_ignore_path(p):
                continue
            if is_never_touch(p, root):
                continue
            candidates.append(p)

    # Rule A: bucket root-level files (always)
    for p in sorted([c for c in candidates if c.parent == root]):
        dest_dir = _bucket_for_file(p.name, buckets)
        if not dest_dir:
            continue
        dst = root / dest_dir / p.name
        dst = _unique_dst(dst)
        if dst.exists():
            notes.append(f"SKIP (exists): {p.name} → {safe_relpath(dst, root)}")
            continue
        ensure_dir(dest_dir)
        ops.append(MoveOp("move", str(p), str(dst), reason=f"Bucket root file into {dest_dir}/"))

    if not deep:
        # only shallow bucketing
        for drel in sorted(mkdirs):
            ops.insert(0, MoveOp("mkdir", None, str((root / drel)), reason="Create bucket directory"))
        if not ops:
            notes.append("No safe moves proposed (shallow).")
        else:
            notes.append("Shallow plan: root-level bucketing only.")
        notes.append("Recommendation: commit before applying.")
        return LayoutPlan(str(root), now_ts(), policy, notes, ops)

    # Deep mode additions:
    # Rule B: bucket SAFE file types found anywhere (excluding already-in-bucket)
    bucket_roots = {b for _, b in buckets}
    bucket_roots_norm = {norm_slashes(b).strip("/") for b in bucket_roots}

    def in_bucket_dir(p: Path) -> bool:
        rel = norm_slashes(safe_relpath(p.parent, root))
        # if a file already lives under a bucket root, skip
        for b in bucket_roots_norm:
            if rel == b or rel.startswith(b + "/"):
                return True
        return False

    deep_moves = 0
    for p in sorted([c for c in candidates if c.is_file() and c.parent != root]):
        if in_bucket_dir(p):
            continue

        # Bucket safe types (docs/config/notebooks/scripts/assets)
        dest_dir = _bucket_for_file(p.name, buckets)

        # Special: python scripts
        if p.suffix.lower() == ".py":
            # only move .py if it is a loose script AND in junk zone
            rel_parent = norm_slashes(safe_relpath(p.parent, root)).lower()
            parent_parts = set([x.lower() for x in Path(rel_parent).parts])
            in_junk = any(j in parent_parts for j in junk_names)
            if in_junk and (not is_in_python_package(p, root)):
                dest_dir = "tools/loose_scripts"
            else:
                dest_dir = None  # don't touch code elsewhere

        if not dest_dir:
            continue

        # Additional constraint: do not move files that would collide often
        dst = root / dest_dir / p.name
        dst = _unique_dst(dst)

        # refuse if still exists
        if dst.exists():
            notes.append(f"SKIP (exists): {safe_relpath(p, root)} → {safe_relpath(dst, root)}")
            continue

        ensure_dir(dest_dir)
        ops.append(MoveOp("move", str(p), str(dst), reason=f"Deep bucket: {safe_relpath(p, root)} → {dest_dir}/"))
        deep_moves += 1

        # Keep plan size sane (avoid gigantic moves without refinement)
        if deep_moves >= 3000:
            notes.append("STOP: plan capped at 3000 deep moves. Refine policy if needed.")
            break

    # Rule C: junk zone non-code consolidation into _quarantine/ (safe types only)
    quarantine_moves = 0
    for p in sorted(candidates):
        rel_parent = norm_slashes(safe_relpath(p.parent, root)).lower()
        parent_parts = set([x.lower() for x in Path(rel_parent).parts])
        if not any(j in parent_parts for j in junk_names):
            continue
        if in_bucket_dir(p):
            continue
        # only non-code in junk zones
        if p.suffix.lower() in (".py", ".pyi", ".js", ".ts", ".java", ".c", ".cpp", ".rs", ".go"):
            continue
        qdir = f"_quarantine/{rel_parent}".strip("/").replace("..", "_")
        dst = root / qdir / p.name
        dst = _unique_dst(dst)
        if dst.exists():
            continue
        ensure_dir(qdir)
        ops.append(MoveOp("move", str(p), str(dst), reason="Junk zone consolidation (non-code)"))
        quarantine_moves += 1
        if quarantine_moves >= 1000:
            notes.append("STOP: quarantine moves capped at 1000.")
            break

    # Prepend mkdir ops
    for drel in sorted(mkdirs):
        dpath = (root / drel).resolve()
        if not dpath.exists():
            ops.insert(0, MoveOp("mkdir", None, str(dpath), reason="Create bucket directory"))

    if not ops:
        notes.append("No safe moves proposed (deep).")
    else:
        notes.append("Deep plan rules enforced:")
        notes.append("- No deletes, no overwrites")
        notes.append("- Never touches archive/ and rhythm_os/data/")
        notes.append("- Moves only safe file types across tree")
        notes.append("- Python files move ONLY if loose + in junk zone + not in package")
        notes.append("Recommendation: commit before applying; review plan JSON first.")

    return LayoutPlan(str(root), now_ts(), policy, notes, ops)

def save_plan(plan: LayoutPlan, out_path: Path) -> None:
    obj = {
        "root": plan.root,
        "created_at": plan.created_at,
        "policy": plan.policy,
        "notes": plan.notes,
        "ops": [dataclasses.asdict(op) for op in plan.ops],
    }
    out_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def load_plan(plan_path: Path) -> LayoutPlan:
    obj = json.loads(plan_path.read_text(encoding="utf-8"))
    ops = [MoveOp(**op) for op in obj.get("ops", [])]
    return LayoutPlan(
        root=obj["root"],
        created_at=obj.get("created_at", ""),
        policy=obj.get("policy", {}),
        notes=obj.get("notes", []),
        ops=ops,
    )

def apply_plan(plan: LayoutPlan) -> Tuple[bool, str]:
    root = Path(plan.root).resolve()
    for op in plan.ops:
        if op.op == "mkdir":
            dst = Path(op.dst).resolve()
            if not is_subpath(dst, root):
                return False, f"Refusing mkdir outside root: {op.dst}"
            dst.mkdir(parents=True, exist_ok=True)
        elif op.op == "move":
            src = Path(op.src).resolve()
            dst = Path(op.dst).resolve()
            if not is_subpath(src, root) or not is_subpath(dst, root):
                return False, f"Refusing move outside root: {op.src} → {op.dst}"
            if not src.exists():
                return False, f"Missing src: {op.src}"
            if dst.exists():
                return False, f"Refusing overwrite (dst exists): {op.dst}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        else:
            return False, f"Unknown op: {op.op}"
    return True, "Plan applied successfully."

# ──────────────────────────────────────────────────────────────
# SignalHydroSystem (ops loop)
# ──────────────────────────────────────────────────────────────
class SignalHydroSystem:
    def __init__(self, root: Optional[str] = None):
        self.mode = "RUN"
        self.current_truth_state = "OBSERVE_ONLY"
        self.gate_lineage: List[Dict[str, Any]] = []
        self.reservoir = deque(maxlen=12)
        self.repo_root = Path(root).resolve() if root else None

        self.river_intake = HydroAgent(
            "River Intake",
            "Observe raw external signals honestly. Do not invent, moralize, or interpret. Output a short literal restatement only.",
            model=LIGHT_MODEL,
        )
        self.forebay = HydroAgent(
            "Forebay Strainer",
            "Clean and normalize the signal. Remove fluff. Output a sealed canonical payload suitable for later processing. No advice.",
            model=PRIMARY_MODEL,
        )
        self.reservoir_keeper = HydroAgent(
            "Reservoir Keeper",
            "Given recent canonical payloads and reservoir size, report pressure as LOW/MED/HIGH and note drift/decay succinctly.",
            model=PRIMARY_MODEL,
        )
        self.dam_engineer = HydroAgent(
            "Dam Engineer",
            "Enforce invariants and boundaries. If unsafe/ambiguous/incoherent, state which flags apply. Keep it brief.",
            model=PRIMARY_MODEL,
        )
        self.truth_facts_agent = HydroAgent(
            "Truth Facts Extractor",
            "Return JSON ONLY with booleans for keys:\n"
            "invariants_ok, pressure_high, overload, ambiguity, incoherent, maintenance_due,\n"
            "human_requested_action, service_window_only, conflict_detected\n"
            "No extra keys. No prose. No code fences.",
            model=PRIMARY_MODEL,
        )
        self.spillway = HydroAgent(
            "Spillway",
            "Handle overload/incoherence/ambiguity by refusing safely. Output a brief refusal + what to watch next. No execution.",
            model=LIGHT_MODEL,
        )
        self.turbines = HydroAgent(
            "Turbines",
            "Given a sealed payload and a truth state, produce useful output. If state is PROPOSE_ALLOWED, output a work proposal only.",
            model=PRIMARY_MODEL,
        )
        self.tailrace = HydroAgent(
            "Tailrace",
            "Publish final output with provenance. Include: truth_state, payload_seal, and gate_lineage summary. Be concise.",
            model=PRIMARY_MODEL,
        )
        self.system_engineer = HydroAgent(
            "System Engineer",
            "Generate an INERT maintenance work list as JSON array of items. Each item includes: id, title, type, tier, risk, reversibility, affected_paths.",
            model=PRIMARY_MODEL,
        )

    def request_human_gate(self, purpose: str, scope: str) -> Tuple[bool, Dict[str, Any]]:
        print(f"\n[GATE WARDEN] → Human required")
        print(f"  Purpose : {purpose}")
        print(f"  Scope   : {scope}")
        sig = input("Enter signature (name/time) or 'deny': ").strip()
        entry = {"purpose": purpose, "scope": scope, "signed": sig, "time": now_ts()}
        if sig.lower() in ("deny", "n", "no"):
            entry["signed"] = "DENIED"
            return False, entry
        self.gate_lineage.append(entry)
        return True, entry

    def homecoming(self):
        print("[HOMECOMING] Daily reset → clearing reservoir & expiring entitlement.")
        self.reservoir.clear()
        self.gate_lineage = []
        self.current_truth_state = "OBSERVE_ONLY"
        self.mode = "RUN"

    def _pressure_numeric(self) -> float:
        return len(self.reservoir) / float(self.reservoir.maxlen)

    def process_signal(self, raw_signal: str, human_requested_action: bool = False) -> str:
        print(f"\n[SYSTEM] Mode: {self.mode} | Truth: {self.current_truth_state}")
        print(f"  Raw signal → {raw_signal[:120]}{'...' if len(raw_signal) > 120 else ''}")

        observed = self.river_intake.think(raw_signal)
        cleaned = self.forebay.think(observed)
        seal = sha16(cleaned)
        print(f"  Forebay sealed: {seal}")

        self.reservoir.append(cleaned)
        pnum = self._pressure_numeric()

        pressure_report = self.reservoir_keeper.think(
            f"Reservoir size: {len(self.reservoir)}/{self.reservoir.maxlen} ({pnum:.2f})."
        )

        constraints = self.dam_engineer.think(
            f"PAYLOAD:\n{cleaned}\nPRESSURE_REPORT:{pressure_report}\nPRESSURE_NUMERIC:{pnum:.2f}"
        )

        facts_prompt = (
            f"MODE:{self.mode}\n"
            f"HUMAN_REQUESTED_ACTION:{bool(human_requested_action)}\n"
            f"PRESSURE_NUMERIC:{pnum:.2f}\n"
            f"CONSTRAINT_NOTES:{constraints}\n"
            "Rules:\n"
            "- pressure_high true if PRESSURE_NUMERIC >= 0.75\n"
            "- overload true if PRESSURE_NUMERIC >= 0.95 or notes mention overload/spill/flood\n"
            "- service_window_only true if MODE is SERVICE\n"
            "- maintenance_due true if MODE is SERVICE or notes mention maintenance/debt/entropy\n"
            "- ambiguity true if notes mention unclear/insufficient\n"
            "- incoherent true if notes mention nonsensical/contradictory\n"
            "- invariants_ok false if notes mention boundary violation/unsafe\n"
            "- conflict_detected true if notes mention disagreement/human refusal\n"
            "Return JSON only."
        )
        ft = self.truth_facts_agent.think(facts_prompt)
        f = parse_truth_facts_llm(ft)
        if f is None:
            f = TruthFacts(invariants_ok=False, incoherent=True)

        # hard truth overrides (digital)
        f.human_requested_action = bool(human_requested_action)
        f.pressure_high = pnum >= 0.75
        f.overload = f.overload or (pnum >= 0.95)
        if self.mode == "SERVICE":
            f.service_window_only = True
            f.maintenance_due = True

        truth_state = resolve_truth_state(f, self.mode)
        if truth_state not in TRUTH_STATES:
            truth_state = "BLOCKED"
        self.current_truth_state = truth_state
        print(f"  Truth state → {truth_state}")

        if truth_state in ("BLOCKED", "EMERGENCY_WATCH", "OBSERVE_ONLY"):
            return self.spillway.think(f"STATE:{truth_state} SEAL:{seal} NOTES:{constraints[:200]}...")

        if truth_state in ("ACTION_ELIGIBLE", "SERVICE_ONLY"):
            approved, entry = self.request_human_gate(
                purpose=f"Execute under {truth_state}",
                scope=f"payload_seal={seal} raw_signal={raw_signal[:80]}..."
            )
            if not approved:
                self.current_truth_state = "EMERGENCY_WATCH"
                return self.spillway.think(
                    f"XOR conflict: {truth_state} eligible but denied. Entry={json.dumps(entry)}"
                )

        turbine_payload = json.dumps({
            "truth_state": truth_state,
            "payload_seal": seal,
            "payload": cleaned,
            "allowed_scope": "propose_only" if truth_state == "PROPOSE_ALLOWED" else "execute_if_signed",
        }, ensure_ascii=False)

        work = self.turbines.think(turbine_payload)

        provenance = {
            "truth_state": truth_state,
            "payload_seal": seal,
            "mode": self.mode,
            "gate_lineage_tail": self.gate_lineage[-3:],
        }
        return self.tailrace.think(f"OUTPUT:\n{work}\nPROVENANCE:\n{json.dumps(provenance, indent=2)}")

    def generate_work_list(self) -> Any:
        txt = self.system_engineer.think(
            "Generate INERT maintenance work list as JSON array ONLY. "
            "No instructions. No sequencing. No execution verbs. "
            "Fields: id,title,type,tier,risk,reversibility,affected_paths."
        )
        try:
            txt2 = re.sub(r"^```json\s*", "", txt.strip())
            txt2 = re.sub(r"\s*```$", "", txt2)
            items = json.loads(txt2)
        except Exception:
            items = {"raw_proposal": txt}
        blob = json.dumps(items).lower()
        for bad in ("execute", "rm -", "del ", "format", "wipe", "overwrite"):
            if bad in blob:
                return {"refused": True, "reason": f"Work list contained forbidden token: {bad}", "raw": txt}
        return items

    # Repo comb tools
    def scan_under_root(self) -> Dict[str, Any]:
        if not self.repo_root:
            raise ValueError("No repo root set. Pass --root.")
        return scan_repo(self.repo_root)

    def propose_layout(self, deep: bool, out_plan_path: str, policy_path: Optional[str]) -> Dict[str, Any]:
        if not self.repo_root:
            raise ValueError("No repo root set. Pass --root.")
        plan = propose_layout_plan(self.repo_root, deep=deep, policy_path=policy_path)
        save_plan(plan, Path(out_plan_path))
        return {
            "saved_plan": out_plan_path,
            "root": plan.root,
            "created_at": plan.created_at,
            "deep": deep,
            "policy": plan.policy,
            "notes": plan.notes,
            "op_count": len(plan.ops),
            "ops_preview": [dataclasses.asdict(op) for op in plan.ops[:30]],
        }

    def apply_layout_plan(self, plan_path: str) -> str:
        if not self.repo_root:
            raise ValueError("No repo root set. Pass --root.")
        plan = load_plan(Path(plan_path))
        if Path(plan.root).resolve() != self.repo_root.resolve():
            return "Refusing: plan root != provided root"

        if self.mode != "SERVICE":
            return "Refusing: layout changes require SERVICE mode."

        approved, _ = self.request_human_gate(
            purpose="Apply layout plan",
            scope=f"plan={plan_path} ops={len(plan.ops)} root={plan.root}"
        )
        if not approved:
            return "Denied: plan not applied."

        ok, msg = apply_plan(plan)
        return msg if ok else f"FAILED: {msg}"

# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Signal Hydro System + Repo Comb (shallow/deep).")
    ap.add_argument("--root", type=str, default=None, help="Repo root (SignalLogic).")
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--work-list", action="store_true")

    ap.add_argument("--propose-layout", action="store_true")
    ap.add_argument("--deep", action="store_true", help="Enable deep safe moves (docs/config/scripts/assets + junk consolidation).")
    ap.add_argument("--policy", type=str, default=None, help="Optional policy JSON file to override buckets/limits.")
    ap.add_argument("--save-plan", type=str, default="layout_plan.json")

    ap.add_argument("--apply-plan", type=str, default=None)
    ap.add_argument("--service-mode", action="store_true")

    args = ap.parse_args()

    system = SignalHydroSystem(root=args.root)
    if args.service_mode:
        system.mode = "SERVICE"

    if args.scan:
        if not args.root:
            print("ERROR: --scan requires --root")
            return 2
        print(json.dumps(system.scan_under_root(), indent=2))
        return 0

    if args.work_list:
        print(json.dumps(system.generate_work_list(), indent=2))
        return 0

    if args.propose_layout:
        if not args.root:
            print("ERROR: --propose-layout requires --root")
            return 2
        out = system.propose_layout(deep=args.deep, out_plan_path=args.save_plan, policy_path=args.policy)
        print(json.dumps(out, indent=2))
        return 0

    if args.apply_plan:
        if not args.root:
            print("ERROR: --apply-plan requires --root")
            return 2
        print(system.apply_layout_plan(args.apply_plan))
        return 0

    if args.interactive:
        print("Signal Hydro System (interactive).")
        print("Commands: homecoming | mode RUN/INSPECT/SERVICE/ARCHIVE | exit")
        print("Tip: prefix a signal with ! to indicate human_requested_action")
        while True:
            raw = input("\nEnter raw signal: ").strip()
            if raw.lower() in ("exit", "quit"):
                print("System shutdown.")
                return 0
            if raw.lower() == "homecoming":
                system.homecoming()
                continue
            if raw.lower().startswith("mode "):
                m = raw.split(" ", 1)[1].strip().upper()
                if m in SYSTEM_MODES:
                    system.mode = m
                    print(f"[SYSTEM] Mode set → {m}")
                else:
                    print(f"[SYSTEM] Unknown mode: {m}")
                continue

            human_action = False
            if raw.startswith("!"):
                human_action = True
                raw = raw[1:].lstrip()

            out = system.process_signal(raw, human_requested_action=human_action)
            print("\n[TAILRACE OUTPUT]\n", out)
            print("-" * 80)

        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
EOF


