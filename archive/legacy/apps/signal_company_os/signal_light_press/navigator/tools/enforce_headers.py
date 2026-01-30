#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml  # pip install pyyaml
except Exception as e:
    raise SystemExit("Missing dependency: pyyaml. Install with: pip install pyyaml") from e


SEAL_DIVIDER = "────────────────────────────────────────"


@dataclass
class DocFinding:
    path: Path
    doc_class: str
    missing_fields: List[str]
    has_seal: bool
    header_ok: bool


def load_policy(policy_path: Path) -> dict:
    with policy_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_excluded(path: Path, exclude_globs: List[str]) -> bool:
    p = str(path.as_posix())
    return any(fnmatch.fnmatch(p, g) for g in exclude_globs)


def infer_doc_class(path: Path) -> str:
    p = path.as_posix()
    if "/codex/canon/" in p or p.endswith("CANON.md"):
        return "canon"
    if "/codex/doctrine/" in p or "DOCTRINE" in path.name:
        return "doctrine"
    if "/codex/guides/" in p or "GUIDE" in path.name:
        return "guide"
    if "/codex/policy/" in p or "POLICY" in path.name:
        return "policy"
    if path.name.upper().startswith("INDEX") or "REGISTER" in path.name.upper():
        return "register"
    return "default"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def extract_header_block(text: str) -> Tuple[str, str]:
    """
    Returns (header, body). Header is assumed to be the initial metadata block
    before the first blank line *after* a leading title line.
    This is intentionally conservative.
    """
    lines = text.splitlines()
    if not lines:
        return "", ""

    # Keep optional title line (e.g., "# Title") inside header region.
    # Header ends at first occurrence of two consecutive blank lines,
    # or when we hit a markdown horizontal rule.
    header_lines = []
    blank_run = 0
    for i, line in enumerate(lines):
        header_lines.append(line)
        if line.strip() == "":
            blank_run += 1
        else:
            blank_run = 0
        if blank_run >= 2:
            body = "\n".join(lines[i + 1 :])
            header = "\n".join(header_lines).rstrip() + "\n"
            return header, body
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line.strip()):
            body = "\n".join(lines[i + 1 :])
            header = "\n".join(header_lines).rstrip() + "\n"
            return header, body

    return text, ""


def header_has_field(header: str, field: str) -> bool:
    # Match "Field: value" anywhere in header region
    return re.search(rf"(?m)^\s*{re.escape(field)}\s*:\s*.+$", header) is not None


def find_seal(text: str) -> bool:
    return re.search(rf"(?m)^\s*SEAL\s*$", text) is not None


def compute_sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_header(header: str, required_fields: List[str], header_contract_path: str) -> Tuple[str, List[str]]:
    """
    Ensures required fields exist (inserts placeholders if missing).
    Also injects Header Contract pointer if absent.
    Returns (new_header, inserted_fields)
    """
    inserted = []
    lines = header.splitlines()

    # Ensure "Header Contract:" line exists (presentation binding)
    if not re.search(r"(?m)^\s*Header Contract\s*:\s*.+$", header):
        # Insert after first non-empty line (often title) or at top
        insert_at = 0
        for i, ln in enumerate(lines):
            if ln.strip():
                insert_at = i + 1
                break
        lines.insert(insert_at, f"Header Contract: {header_contract_path}")
        inserted.append("Header Contract")

    # Ensure required metadata fields
    # Insert near top after title + Header Contract line
    for field in required_fields:
        if field == "Header Contract":
            continue
        if not any(re.match(rf"^\s*{re.escape(field)}\s*:", ln) for ln in lines):
            # Insert with placeholder
            lines.insert(2, f"{field}: TODO")
            inserted.append(field)

    # Clean excessive blank runs in header block
    # (keep at most one blank line)
    cleaned = []
    blank = False
    for ln in lines:
        if ln.strip() == "":
            if blank:
                continue
            blank = True
        else:
            blank = False
        cleaned.append(ln)

    return "\n".join(cleaned).rstrip() + "\n\n", inserted


def append_seal_block(text: str, path: Path, doc_class: str) -> str:
    """
    Appends a seal block if not present. Conservative: does not rewrite existing seals.
    """
    if find_seal(text):
        return text

    today = datetime.utcnow().strftime("%Y-%m-%d")
    seal_type = {
        "canon": "CANONICAL SEAL",
        "policy": "POLICY SEAL",
        "register": "CANONICAL REGISTER SEAL",
        "doctrine": "DOCTRINE SEAL",
        "guide": "GUIDE SEAL",
        "default": "SEAL",
    }.get(doc_class, "SEAL")

    content_hash = compute_sha256(text)

    seal = (
        f"\n{SEAL_DIVIDER}\n"
        f"SEAL\n\n"
        f"Document: {path.name}\n"
        f"Class: {doc_class}\n"
        f"Seal Type: {seal_type}\n"
        f"Authority: Signal Light Press\n"
        f"Date Sealed: {today}\n"
        f"Content SHA256: {content_hash}\n\n"
        f"No silent amendments.\n"
        f"{SEAL_DIVIDER}\n"
    )
    return text.rstrip() + "\n" + seal


def iter_authoritative_files(repo_root: Path, roots: List[str], exclude_globs: List[str]) -> List[Path]:
    out = []
    for r in roots:
        root_path = repo_root / r
        if not root_path.exists():
            continue
        for p in root_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".yaml", ".yml"):
                if is_excluded(p.relative_to(repo_root), exclude_globs):
                    continue
                out.append(p)
    return out


def audit(repo_root: Path, policy: dict) -> List[DocFinding]:
    files = iter_authoritative_files(repo_root, policy["authoritative_roots"], policy["exclude_globs"])
    findings: List[DocFinding] = []
    for f in files:
        text = read_text(f)
        header, _body = extract_header_block(text)
        doc_class = infer_doc_class(f)
        required = policy["required_fields"].get(doc_class, policy["required_fields"]["default"])
        missing = [fld for fld in required if not header_has_field(header, fld)]
        findings.append(
            DocFinding(
                path=f,
                doc_class=doc_class,
                missing_fields=missing,
                has_seal=find_seal(text),
                header_ok=(len(missing) == 0),
            )
        )
    return findings


def apply(repo_root: Path, policy: dict, do_seal: bool, dry_run: bool) -> List[DocFinding]:
    findings = audit(repo_root, policy)
    for fd in findings:
        if fd.path.suffix.lower() not in (".md", ".txt"):
            continue  # do not rewrite yaml
        text = read_text(fd.path)
        header, body = extract_header_block(text)
        required = policy["required_fields"].get(fd.doc_class, policy["required_fields"]["default"])
        new_header, inserted = normalize_header(header, required, policy["header_contract_path"])

        new_text = new_header + body.lstrip("\n")
        if do_seal and fd.doc_class in policy.get("seal_allowed_classes", []):
            new_text = append_seal_block(new_text, fd.path, fd.doc_class)

        if new_text != text and not dry_run:
            write_text_atomic(fd.path, new_text)

    return audit(repo_root, policy)


def write_report(findings: List[DocFinding], report_path: Path) -> None:
    lines = []
    bad = 0
    for f in sorted(findings, key=lambda x: str(x.path)):
        if not f.header_ok:
            bad += 1
            lines.append(f"- FAIL header: {f.path}  (class={f.doc_class}) missing={f.missing_fields}")
    lines.append("")
    lines.append(f"Total files audited: {len(findings)}")
    lines.append(f"Header violations: {bad}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Signal Light Press header/seal enforcement tool")
    ap.add_argument("mode", choices=["audit", "apply"])
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--policy", default="signal_light_press/navigator/header_policy.yaml")
    ap.add_argument("--seal", action="store_true", help="Append seal block where allowed")
    ap.add_argument("--dry-run", action="store_true", help="Do not write changes")
    ap.add_argument("--report", default="signal_light_press/AUDIT_HEADERS_REPORT.md")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = load_policy(repo_root / args.policy)
    roots = policy.get("authoritative_roots", [])

    print("AUTHORITATIVE ROOTS LOADED:")
    for r in roots:
        print(" -", r)


    if args.mode == "audit":
        findings = audit(repo_root, policy)
        write_report(findings, repo_root / args.report)
        violations = [f for f in findings if not f.header_ok]
        if violations:
            raise SystemExit(f"Header audit failed: {len(violations)} violations. See {args.report}")
        print("Header audit clean.")
        return

    if args.mode == "apply":
        findings = apply(repo_root, policy, do_seal=args.seal, dry_run=args.dry_run)
        write_report(findings, repo_root / args.report)
        violations = [f for f in findings if not f.header_ok]
        if violations:
            raise SystemExit(f"Apply complete, but {len(violations)} header violations remain. See {args.report}")
        print("Apply complete. Headers are compliant.")
        return


if __name__ == "__main__":
    main()
