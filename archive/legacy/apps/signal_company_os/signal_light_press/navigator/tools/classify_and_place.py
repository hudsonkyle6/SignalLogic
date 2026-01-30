#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Canonical enums (explicit, non-negotiable)
# ──────────────────────────────────────────────────────────────────────────────

DOCUMENT_KINDS = {
    "canon",
    "doctrine",
    "reference",
    "instrument",
    "artifact",
    "test",
    "publication",
}

ROLES = {
    "renderer",
    "emitter",
    "engine",
    "simulation",
    "guide",
    "policy",
}

# ──────────────────────────────────────────────────────────────────────────────
# Canonical resolution table (mirror of existing doctrine)
# ──────────────────────────────────────────────────────────────────────────────

CANONICAL_RESOLUTION = {
    ("instrument", "renderer"): {
        "path": "visibility/renderers/",
        "header": ".header_reference.md",
        "seal_required": False,
        "verification_required": True,
        "authority": "None",
        "computation": "Forbidden",
    },
    ("reference", None): {
        "path": "codex/references/",
        "header": ".header_reference.md",
        "seal_required": False,
        "verification_required": False,
        "authority": "None",
        "computation": "Forbidden",
    },
    ("doctrine", None): {
        "path": "codex/doctrine/",
        "header": ".header_DOCTRINAL_MIRROR.md",
        "seal_required": True,
        "verification_required": False,
        "authority": "Doctrinal",
        "computation": "Forbidden",
    },
    ("canon", None): {
        "path": "codex/canon/",
        "header": ".header_root_canon.md",
        "seal_required": True,
        "verification_required": False,
        "authority": "Canonical",
        "computation": "Forbidden",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def abort(msg: str) -> None:
    print(f"\nERROR: {msg}\n")
    sys.exit(1)


def prompt_choice(label: str, choices: set[str]) -> str:
    print(f"\n{label}")
    for c in sorted(choices):
        print(f"  - {c}")
    val = input("> ").strip().lower()
    if val not in choices:
        abort(f"Invalid choice '{val}'. Allowed: {sorted(choices)}")
    return val


def prompt_bool(label: str) -> bool:
    val = input(f"{label} [y/n]: ").strip().lower()
    if val not in {"y", "n"}:
        abort("Expected 'y' or 'n'")
    return val == "y"


def resolve(kind: str, role: Optional[str]) -> dict:
    key = (kind, role)
    fallback = (kind, None)

    if key in CANONICAL_RESOLUTION:
        return CANONICAL_RESOLUTION[key]
    if fallback in CANONICAL_RESOLUTION:
        return CANONICAL_RESOLUTION[fallback]

    abort(
        f"No canonical resolution for kind='{kind}' role='{role}'. "
        "Classification is ambiguous or forbidden."
    )


def scaffold(base: Path, name: str, header_template: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    doc = base / f"{name}.md"

    if doc.exists():
        abort(f"Refusing to overwrite existing file: {doc}")

    if not header_template.exists():
        abort(f"Header template not found: {header_template}")

    doc.write_text(header_template.read_text(), encoding="utf-8")
    print(f"✔ Created {doc}")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical classification and placement navigator (hybrid)"
    )
    parser.add_argument("--name", help="Document or instrument name (e.g. SIGNAL_SCOPE_V2)")
    parser.add_argument("--kind", choices=DOCUMENT_KINDS)
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument("--observational", choices=["true", "false"])
    parser.add_argument("--computational", choices=["true", "false"])
    parser.add_argument("--scaffold", action="store_true")
    parser.add_argument("--root", default=".", help="Repo root (default: .)")

    args = parser.parse_args()

    # ── Hybrid prompting ───────────────────────────────────────────────────────
    name = args.name or input("Name: ").strip()
    if not name:
        abort("Name is required")

    kind = args.kind or prompt_choice("Select document kind:", DOCUMENT_KINDS)

    role = args.role
    if kind == "instrument" and role is None:
        role = prompt_choice("Select instrument role:", ROLES)

    observational = (
        args.observational == "true"
        if args.observational is not None
        else prompt_bool("Is this observational?")
    )

    computational = (
        args.computational == "true"
        if args.computational is not None
        else prompt_bool("Is this computational?")
    )

    # ── Hard guards ────────────────────────────────────────────────────────────
    if kind == "instrument" and computational:
        abort("Instruments cannot be computational")

    # ── Resolve canonically ────────────────────────────────────────────────────
    resolved = resolve(kind, role)
    root = Path(args.root).resolve()
    target_path = root / resolved["path"] / name.lower()

    header_template = root / resolved["header"]

    # ── Report ─────────────────────────────────────────────────────────────────
    print("\nCANONICAL CLASSIFICATION RESULT")
    print("──────────────────────────────")
    print(f"Name: {name}")
    print(f"Kind: {kind}")
    print(f"Role: {role}")
    print(f"Observational: {observational}")
    print(f"Computational: {computational}")
    print("\nResolved:")
    print(f"- Path: {target_path}")
    print(f"- Required Header: {resolved['header']}")
    print(f"- Authority: {resolved['authority']}")
    print(f"- Seal Required: {resolved['seal_required']}")
    print(f"- Verification Required: {resolved['verification_required']}")

    # ── Optional scaffold ──────────────────────────────────────────────────────
    if args.scaffold:
        print("\nScaffolding enabled.")
        scaffold(target_path, name, header_template)
        print("\nNext:")
        print("1. Populate document body")
        print("2. Run: python navigator/tools/enforce_headers.py audit")

    else:
        print("\n(No files created. Use --scaffold to create structure.)")


if __name__ == "__main__":
    main()
