#!/usr/bin/env python3
from __future__ import annotations
import sys
import argparse
import re
import fnmatch
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
try:
    import yaml
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
except ImportError as e:
    raise SystemExit("Missing deps: pyyaml, cryptography") from e

SEAL_DIVIDER = "────────────────────────────────────────"

@dataclass
class DocFinding:
    path: Path
    doc_class: str
    missing_fields: List[str]
    has_closing_seal: bool
    has_actual_seal: bool
    header_ok: bool

def load_policy(policy_path: Path) -> dict:
    with policy_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def is_excluded(path: Path, exclude_globs: List[str]) -> bool:
    p = str(path.as_posix())
    return any(fnmatch.fnmatch(p, g) for g in exclude_globs)

def infer_doc_class(path: Path) -> str:
    p = path.as_posix().lower()
    if "/canon/" in p or "canon" in path.name.lower():
        return "canon"
    if "/doctrine/" in p or "doctrine" in path.name.lower():
        return "doctrine"
    if "/policy/" in p or "policy" in path.name.lower():
        return "policy"
    if "/guides/" in p or "guide" in path.name.lower():
        return "guide"
    if "/references/" in p or "reference" in path.name.lower():
        return "reference"
    if path.name.lower().startswith("index") or "register" in path.name.lower():
        return "register"
    if "/archive/" in p or "/fieldnotes/" in p:
        return "archive"
    return "default"

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def write_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def extract_header_block(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    header_lines = []
    blank_run = 0
    for i, line in enumerate(lines):
        header_lines.append(line)
        if line.strip() == "":
            blank_run += 1
        else:
            blank_run = 0
        if blank_run >= 2 or re.match(r"^\s*(-{3,}|\*{3,})\s*$", line.strip()):
            return "\n".join(header_lines).rstrip() + "\n", "\n".join(lines[i+1:])
    return text, ""

def header_has_field(header: str, field: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(field)}\s*:\s*.+$", header) is not None

def find_closing_seal(text: str) -> bool:
    return re.search(rf"(?m)^\s*SEAL\s*$", text) is not None

def compute_sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def normalize_header(header: str, required_fields: List[str], defaults: Dict[str, str], header_contract_path: str, doc_class: str) -> tuple[str, List[str]]:
    inserted = []
    lines = header.splitlines()
    if not header_has_field(header, "Header Contract"):
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Header Contract: {header_contract_path}")
        inserted.append("Header Contract")
    existing = {k.strip(): v.strip() for line in lines if ":" in line for k, v in [line.split(":", 1)]}
    for field in required_fields:
        if field not in existing:
            val = defaults.get(field, "TBD")
            if field == "Effective Date" and doc_class == "canon":
                val = "2026-01-28"
            if field == "Scope":
                val = "Signal Light Press — Anchor Vault"
            # Zone-based from fix_headers
            if doc_class == "archive":
                val = defaults.get(field, "ARCHIVED" if field == "Status" else val)
            lines.insert(len(lines) - 1, f"{field}: {val}")
            inserted.append(field)
    cleaned = []
    blank = False
    for ln in lines:
        if not ln.strip():
            if blank:
                continue
            blank = True
        else:
            blank = False
        cleaned.append(ln)
    return "\n".join(cleaned).rstrip() + "\n\n", inserted

def append_closing_seal(text: str, path: Path, doc_class: str) -> str:
    if find_closing_seal(text):
        return text
    today = datetime.utcnow().strftime("%Y-%m-%d")
    seal_type = {"canon": "CANONICAL SEAL", "policy": "POLICY SEAL", "register": "REGISTER SEAL", "default": "SEAL"}.get(doc_class, "SEAL")
    content_hash = compute_sha256(text)
    seal = f"\n{SEAL_DIVIDER}\nSEAL\n\nDocument: {path.name}\nClass: {doc_class}\nSeal Type: {seal_type}\nAuthority: Signal Light Press\nDate Sealed: {today}\nContent SHA256: {content_hash}\n\nNo silent amendments.\n{SEAL_DIVIDER}\n"
    return text.rstrip() + seal

def generate_actual_seal(path: Path, private_key_path: str) -> None:
    content = path.read_bytes()
    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
    signature = private_key.sign(content, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    sig_path = path.with_suffix(path.suffix + ".sig")
    sig_path.write_bytes(signature)

def has_actual_seal(path: Path) -> bool:
    return path.with_suffix(path.suffix + ".sig").exists()

def iter_files(repo_root: Path, roots: List[str], exclude_globs: List[str]) -> List[Path]:
    out = []
    for r in roots:
        root_path = repo_root / r
        if not root_path.exists():
            continue
        for p in root_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".md", ".txt", ".yaml", ".yml"):
                if not is_excluded(p.relative_to(repo_root), exclude_globs):
                    out.append(p)
    return out

def audit(repo_root: Path, policy: dict) -> List[DocFinding]:
    files = iter_files(repo_root, policy["authoritative_roots"], policy["exclude_globs"])
    findings = []
    for f in files:
        text = read_text(f)
        header, _ = extract_header_block(text)
        doc_class = infer_doc_class(f)
        required = policy["required_fields"].get(doc_class, policy["required_fields"]["default"])
        missing = [fld for fld in required if not header_has_field(header, fld)]
        findings.append(DocFinding(
            path=f,
            doc_class=doc_class,
            missing_fields=missing,
            has_closing_seal=find_closing_seal(text),
            has_actual_seal=has_actual_seal(f),
            header_ok=len(missing) == 0,
        ))
    return findings

def apply(repo_root: Path, policy: dict, do_closing_seal: bool, do_actual_seal: bool, dry_run: bool) -> List[DocFinding]:
    findings = audit(repo_root, policy)
    for fd in findings:
        if fd.path.suffix.lower() not in (".md", ".txt"):
            continue
        text = read_text(fd.path)
        header, body = extract_header_block(text)
        required = policy["required_fields"].get(fd.doc_class, policy["required_fields"]["default"])
        defaults = policy["defaults"]
        new_header, _ = normalize_header(header, required, defaults, policy["header_contract_path"], fd.doc_class)
        new_text = new_header + body.lstrip("\n")
        if do_closing_seal and fd.doc_class in policy.get("seal_allowed_classes", []):
            new_text = append_closing_seal(new_text, fd.path, fd.doc_class)
        if new_text != text and not dry_run:
            write_text_atomic(fd.path, new_text)
        if do_actual_seal and not dry_run:
            generate_actual_seal(fd.path, policy.get("crypto_private_key_path", "private.pem"))
    return audit(repo_root, policy)

def write_report(findings: List[DocFinding], report_path: Path) -> None:
    lines = []
    bad = sum(1 for f in findings if not f.header_ok or not f.has_closing_seal or not f.has_actual_seal)
    for f in sorted(findings, key=lambda x: str(x.path)):
        if not f.header_ok:
            lines.append(f"- FAIL header: {f.path} missing={f.missing_fields}")
        if not f.has_closing_seal:
            lines.append(f"- FAIL closing seal: {f.path}")
        if not f.has_actual_seal:
            lines.append(f"- FAIL actual seal: {f.path}")
    lines.append(f"Total audited: {len(findings)}")
    lines.append(f"Violations: {bad}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description="SLP header/seal enforcer")
    ap.add_argument("mode", choices=["audit", "apply"])
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--policy", default="signal_light_press/navigator/policies/header_policy.yaml")
    ap.add_argument("--closing-seal", action="store_true")
    ap.add_argument("--actual-seal", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default="signal_light_press/AUDIT_HEADERS_REPORT.md")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = (repo_root / policy_path).resolve()

    policy = load_policy(policy_path)

    if args.mode == "audit":
        findings = audit(repo_root, policy)
        write_report(findings, repo_root / args.report)
        if any(not f.header_ok or not f.has_closing_seal or not f.has_actual_seal for f in findings):
            sys.exit(1)
        print("Audit clean.")
    elif args.mode == "apply":
        findings = apply(repo_root, policy, args.closing_seal, args.actual_seal, args.dry_run)
        write_report(findings, repo_root / args.report)
        if any(not f.header_ok for f in findings):
            sys.exit(1)
        print("Apply complete.")

if __name__ == "__main__":
    main()
