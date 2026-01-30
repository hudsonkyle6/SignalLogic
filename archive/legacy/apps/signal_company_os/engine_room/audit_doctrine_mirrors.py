#!/usr/bin/env python3
"""
Doctrinal Mirror Content Auditor
Signal Light Press

Descriptive-only audit tool.
Emits findings; human adjudication required.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
MIRROR_DIR = ROOT / "apps/signal_company_os/signal_light_press/codex/doctrine_mirror"

REQUIRED_MIRROR_MARKERS = [
    "DOCTRINAL MIRROR NOTICE",
    "Source Authority:",
    "Canonical Source:",
    "Mirror Location:",
    "READ-ONLY MIRROR",
]

INTERPRETIVE_RISK_PHRASES = [
    "guide",
    "how to",
    "should",
    "we recommend",
    "best practice",
    "this document explains how",
]

def audit_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")

    findings = {
        "file": path.name,
        "has_mirror_notice": all(m in text for m in REQUIRED_MIRROR_MARKERS),
        "canonical_source_present": "Canonical Source:" in text,
        "interpretive_risk": [],
        "scope_risk": False,
    }

    for phrase in INTERPRETIVE_RISK_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            findings["interpretive_risk"].append(phrase)

    # crude scope heuristic (flag only)
    if "Reader" in path.name or "Guide" in path.name or "INDEX" in path.name:
        findings["scope_risk"] = True

    return findings


def main():
    if not MIRROR_DIR.exists():
        print(f"Mirror directory not found: {MIRROR_DIR}")
        sys.exit(1)

    print("# Doctrinal Mirror Audit Report\n")

    for file in sorted(MIRROR_DIR.glob("*.md")):
        r = audit_file(file)

        print(f"## {r['file']}")
        print(f"- Mirror notice present: {'YES' if r['has_mirror_notice'] else 'NO'}")
        print(f"- Canonical source cited: {'YES' if r['canonical_source_present'] else 'NO'}")

        if r["interpretive_risk"]:
            print(f"- ⚠ Interpretive language detected: {', '.join(r['interpretive_risk'])}")
        else:
            print(f"- Interpretive language detected: none")

        if r["scope_risk"]:
            print("- ⚠ Scope risk: filename suggests interpretive/reference document")

        print()

if __name__ == "__main__":
    main()
