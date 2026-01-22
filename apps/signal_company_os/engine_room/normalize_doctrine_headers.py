#!/usr/bin/env python3
"""
Doctrine Header Normalizer
Signal Light Press

- Replaces ONLY the header block
- Preserves body verbatim
- Requires explicit metadata
- Fails if header/body boundary is unclear
- Operates only within Signal Light Press scope
"""

from pathlib import Path
import sys

# =========================
# HEADER TEMPLATES (LOCKED)
# =========================

MIRROR_TEMPLATE = """📜 {title}

DOCTRINAL MIRROR NOTICE

Source Authority:
Signal Light Press

Canonical Source:
{canonical_source}

Mirror Location:
{mirror_path}

Status:
READ-ONLY MIRROR

Modification Rule:
This file may not be edited independently.
All changes must originate from the Canonical Source.

Enforcement Role:
This mirror exists solely to support enforcement,
interpretation limits, and runtime integrity.

Violation Notice:
Any divergence from the Canonical Source
constitutes a canonical breach.
"""

CANON_TEMPLATE = """📜 {title}

Authority: Signal Light Press
Classification: {classification}
Status: CANONICAL
Domain: {domain}
Applies To: {applies_to}
Amendment Rule: Signal Light Press only
Executable: No
"""

# =========================
# CORE LOGIC
# =========================

def split_header_body(text: str) -> tuple[str, str]:
    """
    Splits document into (header, body) at the first blank line.
    Fails if no clear boundary exists.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "":
            header = "\n".join(lines[:i])
            body = "\n".join(lines[i + 1 :])
            return header, body
    raise ValueError("No blank line separating header and body")


def normalize_file(
    file_path: Path,
    mode: str,
    metadata: dict,
    dry_run: bool = False,
):
    original = file_path.read_text(encoding="utf-8")

    _, body = split_header_body(original)

    if mode == "mirror":
        header = MIRROR_TEMPLATE.format(**metadata)
    elif mode == "canon":
        header = CANON_TEMPLATE.format(**metadata)
    else:
        raise ValueError("Mode must be 'mirror' or 'canon'")

    new_text = header.rstrip() + "\n\n" + body.lstrip()

    if dry_run:
        print(f"\n--- {file_path} (DRY RUN) ---\n")
        print(new_text[:800])
        return

    file_path.write_text(new_text, encoding="utf-8")
    print(f"✔ normalized: {file_path}")


# =========================
# CLI ENTRY (SEALED)
# =========================

def main():
    if len(sys.argv) < 3:
        print("Usage: normalize_doctrine_headers.py <mirror|canon> <relative_file_path>")
        sys.exit(1)

    mode = sys.argv[1]
    relative_path = sys.argv[2]

    # ---------------------------------
    # PATH RESOLUTION (NON-NEGOTIABLE)
    # ---------------------------------

    REPO_ROOT = Path(__file__).resolve().parents[3]
    SLP_ROOT = REPO_ROOT / "apps" / "signal_company_os" / "signal_light_press"

    file_path = (SLP_ROOT / relative_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if SLP_ROOT not in file_path.parents:
        raise PermissionError("File is outside Signal Light Press scope")

    # ---------------------------------
    # EXPLICIT METADATA (PER FILE ONLY)
    # ---------------------------------

    if mode == "mirror":
        metadata = dict(
            title="BOUNDARY FIELD DOCTRINE",
            canonical_source="signal_light_press/doctrine/BOUNDARY_FIELD_DOCTRINE.md",
            mirror_path=f"codex/doctrine_mirror/{file_path.name}",
        )

    elif mode == "canon":
        metadata = dict(
            title="ASSIST UNDER DISCIPLINE",
            classification="Crown Jewel",
            domain="System Law",
            applies_to="All Engines and Domains",
        )

    else:
        raise ValueError("Mode must be 'mirror' or 'canon'")

    normalize_file(file_path, mode, metadata)


if __name__ == "__main__":
    main()
