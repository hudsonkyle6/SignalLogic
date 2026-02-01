from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve()
# repo root discovery (walk up until .git)
REPO = ROOT
for _ in range(10):
    if (REPO / ".git").exists():
        break
    REPO = REPO.parent

SLP = REPO / "signal_light_press"
OUTDIR = SLP / "fieldnotes" / "audits"
OUTDIR.mkdir(parents=True, exist_ok=True)

GOVERNABLE_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}

REQUIRED_KEYS = [
    "Authority",
    "Classification",
    "Status",
    "Domain",
    "Applies To",
    "Amendment Rule",
    "Executable",
]

HEADER_KEY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z \-]+)\s*:\s*(.*?)\s*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

SEAL_HINT_RE = re.compile(r"\bSEAL\b|\bCLOSER\b|\bCLOSE\b", re.IGNORECASE)

def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO.resolve()))
    except Exception:
        return str(p)

@dataclass
class HeaderParse:
    ok: bool
    found: Dict[str, str]
    missing: List[str]
    raw_lines: int

def parse_header(text: str) -> HeaderParse:
    """
    Reads the first ~80 lines looking for YAML-ish "Key: Value" lines.
    Stops early if it hits an obvious body marker (blank gap > 2 or markdown heading).
    """
    lines = text.splitlines()
    found: Dict[str, str] = {}
    scanned = 0
    blanks = 0
    for i, line in enumerate(lines[:120]):
        scanned += 1
        if line.strip() == "":
            blanks += 1
            if blanks >= 3 and found:
                break
            continue
        if line.lstrip().startswith("#") and found:
            break

        m = HEADER_KEY_RE.match(line)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            found[k] = v
            blanks = 0

    missing = [k for k in REQUIRED_KEYS if k not in found]
    ok = (len(missing) == 0)
    return HeaderParse(ok=ok, found=found, missing=missing, raw_lines=scanned)

def looks_like_archive(path: Path) -> bool:
    p = rel(path).replace("\\", "/").lower()
    return p.startswith("signal_light_press/archive/") or "/archive/" in p

def gather_files() -> List[Path]:
    files: List[Path] = []
    for p in SLP.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in GOVERNABLE_SUFFIXES:
            continue
        files.append(p)
    return sorted(files)

def check_md_links(path: Path, text: str) -> List[Dict[str, str]]:
    """
    Best-effort markdown link check for relative links to local files.
    Ignores http(s), mailto, anchors-only.
    """
    broken = []
    base = path.parent
    for m in MD_LINK_RE.finditer(text):
        target = m.group(2).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            continue
        target = target.split("#", 1)[0].strip()
        if not target:
            continue
        tpath = (base / target).resolve()
        if not tpath.exists():
            broken.append({"source": rel(path), "target": target})
    return broken

def main() -> int:
    files = gather_files()

    report = {
        "repo": str(REPO),
        "slp_root": str(SLP),
        "counts": {
            "governable_files": len(files),
        },
        "files": [],
        "missing_headers": [],
        "archive_files": [],
        "duplicates": [],
        "broken_links": [],
        "summary": {},
    }

    hash_map: Dict[str, List[str]] = {}

    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""

        hp = parse_header(text)
        seal_hint = bool(SEAL_HINT_RE.search(text[-6000:]))  # look near end-ish, not perfect
        sha = file_sha256(p)

        hash_map.setdefault(sha, []).append(rel(p))

        entry = {
            "path": rel(p),
            "sha256": sha,
            "archive": looks_like_archive(p),
            "header_ok": hp.ok,
            "missing": hp.missing,
            "header": hp.found,
            "seal_hint": seal_hint,
        }
        report["files"].append(entry)

        if entry["archive"]:
            report["archive_files"].append(entry["path"])
        if not hp.ok:
            report["missing_headers"].append({"path": entry["path"], "missing": hp.missing})

        if p.suffix.lower() == ".md":
            report["broken_links"].extend(check_md_links(p, text))

    # duplicates
    for sha, paths in hash_map.items():
        if len(paths) > 1:
            report["duplicates"].append({"sha256": sha, "paths": paths})

    # summary
    report["summary"] = {
        "missing_header_files": len(report["missing_headers"]),
        "archive_files": len(report["archive_files"]),
        "duplicate_sets": len(report["duplicates"]),
        "broken_link_count": len(report["broken_links"]),
    }

    out_json = OUTDIR / "SLP_DOCTRINE_AUDIT.json"
    out_md = OUTDIR / "SLP_DOCTRINE_AUDIT.md"

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # lightweight markdown
    lines = []
    lines.append("# Signal Light Press — Doctrine Audit")
    lines.append("")
    lines.append(f"- Governable files: **{report['counts']['governable_files']}**")
    lines.append(f"- Missing headers: **{report['summary']['missing_header_files']}**")
    lines.append(f"- Archive files: **{report['summary']['archive_files']}**")
    lines.append(f"- Duplicate sets: **{report['summary']['duplicate_sets']}**")
    lines.append(f"- Broken links: **{report['summary']['broken_link_count']}**")
    lines.append("")

    if report["missing_headers"]:
        lines.append("## Missing Header Keys")
        for item in report["missing_headers"][:80]:
            lines.append(f"- {item['path']}  missing={item['missing']}")
        if len(report["missing_headers"]) > 80:
            lines.append(f"- …and {len(report['missing_headers'])-80} more")
        lines.append("")

    if report["duplicates"]:
        lines.append("## Duplicate Content (SHA-256 match)")
        for d in report["duplicates"][:50]:
            lines.append(f"- sha={d['sha256'][:16]}…")
            for p in d["paths"]:
                lines.append(f"  - {p}")
        if len(report["duplicates"]) > 50:
            lines.append(f"- …and {len(report['duplicates'])-50} more sets")
        lines.append("")

    if report["broken_links"]:
        lines.append("## Broken Markdown Links (best-effort)")
        for b in report["broken_links"][:120]:
            lines.append(f"- {b['source']} → {b['target']}")
        if len(report["broken_links"]) > 120:
            lines.append(f"- …and {len(report['broken_links'])-120} more")
        lines.append("")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE: {rel(out_json)}")
    print(f"WROTE: {rel(out_md)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
