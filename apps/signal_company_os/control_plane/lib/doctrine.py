from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

HEADER_KEY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z \-]+)\s*:\s*(.*?)\s*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_header(
    text: str, required_keys: List[str]
) -> Tuple[bool, Dict[str, str], List[str]]:
    lines = text.splitlines()
    found: Dict[str, str] = {}
    blanks = 0
    for ln in lines[:140]:
        if ln.strip() == "":
            blanks += 1
            if blanks >= 3 and found:
                break
            continue
        if ln.lstrip().startswith("#") and found:
            break
        m = HEADER_KEY_RE.match(ln)
        if m:
            found[m.group(1).strip()] = m.group(2).strip()
            blanks = 0
    missing = [k for k in required_keys if k not in found]
    return (len(missing) == 0), found, missing


def broken_links(md_path: Path, text: str) -> List[Dict[str, str]]:
    out = []
    base = md_path.parent
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
            out.append({"source": str(md_path), "target": target})
    return out


def compile_slp(
    slp_root: Path, suffixes: List[str], required_keys: List[str], out_dir: Path
) -> Dict[str, Any]:
    files: List[Path] = []
    for p in slp_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {s.lower() for s in suffixes}:
            files.append(p)
    files = sorted(files)

    hash_map: Dict[str, List[str]] = {}
    missing: List[Dict[str, Any]] = []
    broken: List[Dict[str, str]] = []
    entries: List[Dict[str, Any]] = []

    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        ok, header, miss = parse_header(text, required_keys)
        sha = sha256_file(p)
        hash_map.setdefault(sha, []).append(str(p))

        if not ok:
            missing.append({"path": str(p), "missing": miss})

        if p.suffix.lower() == ".md":
            broken.extend(broken_links(p, text))

        entries.append(
            {
                "path": str(p),
                "sha256": sha,
                "header_ok": ok,
                "missing": miss,
                "header": header,
            }
        )

    dups = [{"sha256": k, "paths": v} for k, v in hash_map.items() if len(v) > 1]

    report = {
        "slp_root": str(slp_root),
        "counts": {
            "files": len(entries),
            "missing_headers": len(missing),
            "duplicate_sets": len(dups),
            "broken_links": len(broken),
        },
        "missing_headers": missing,
        "duplicates": dups,
        "broken_links": broken,
        "files": entries,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "doctrine_index.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    md = []
    md.append("# Signal Light Press — Doctrine Report")
    md.append("")
    md.append(f"- Files scanned: **{report['counts']['files']}**")
    md.append(f"- Missing headers: **{report['counts']['missing_headers']}**")
    md.append(f"- Duplicate sets: **{report['counts']['duplicate_sets']}**")
    md.append(f"- Broken links: **{report['counts']['broken_links']}**")
    md.append("")
    if missing:
        md.append("## Missing Header Keys")
        for item in missing[:120]:
            md.append(f"- {item['path']}  missing={item['missing']}")
        if len(missing) > 120:
            md.append(f"- …and {len(missing) - 120} more")
        md.append("")
    if dups:
        md.append("## Duplicate Content (sha256)")
        for d in dups[:60]:
            md.append(f"- sha={d['sha256'][:16]}…")
            for p in d["paths"]:
                md.append(f"  - {p}")
        if len(dups) > 60:
            md.append(f"- …and {len(dups) - 60} more")
        md.append("")
    if broken:
        md.append("## Broken Markdown Links (best-effort)")
        for b in broken[:160]:
            md.append(f"- {b['source']} → {b['target']}")
        if len(broken) > 160:
            md.append(f"- …and {len(broken) - 160} more")
        md.append("")
    (out_dir / "doctrine_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    return report
