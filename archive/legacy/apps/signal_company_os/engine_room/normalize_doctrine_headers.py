#!/usr/bin/env python3
"""
Doctrine Header Normalizer
Signal Light Press

- Replaces ONLY the header block
- Preserves body verbatim
- Requires explicit metadata
- Fails if header/body boundary is unclear
- Enforces Signal Light Press scope without path rewriting
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
            return "\n".join(lines[:i]), "\n".join(lines[i + 1 :])
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
        print("Usage: normalize_doctrine_headers.py <mirror|canon> <file_path>")
        sys.exit(1)

    mode = sys.argv[1]
    raw_path = Path(sys.argv[2])

    # ---------------------------------
    # PATH RESOLUTION (AUTHORITATIVE)
    # ---------------------------------

    file_path = raw_path.resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    # ---------------------------------
    # SCOPE ENFORCEMENT (NON-MUTATING)
    # ---------------------------------

    repo_root = Path(__file__).resolve().parents[3]
    slp_root = repo_root / "apps" / "signal_company_os" / "signal_light_press"

    if slp_root not in file_path.parents:
        raise PermissionError(
            f"File is outside Signal Light Press scope: {file_path}"
        )

    # ---------------------------------
    # EXPLICIT METADATA (PER FILE)
    # ---------------------------------

    if mode == "mirror":
        metadata = dict(
            title=file_path.stem.replace("_", " ").upper(),
            canonical_source=f"signal_light_press/doctrine/{file_path.name}",
            mirror_path=f"codex/doctrine_mirror/{file_path.name}",
        )

    elif mode == "canon":
        metadata = dict(
            title=file_path.stem.replace("_", " ").upper(),
            classification="CROWN JEWEL",
            domain="Doctrine",
            applies_to="Signal Company System",
        )

    else:
        raise ValueError("Mode must be 'mirror' or 'canon'")

    normalize_file(file_path, mode, metadata)


if __name__ == "__main__":
    main()
