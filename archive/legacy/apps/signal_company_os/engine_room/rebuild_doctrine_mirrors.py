from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
import shutil
import re


@dataclass(frozen=True)
class MirrorSpec:
    mirror_file: str
    title: str
    canonical_source: str
    enforcement_assertions: list[str]


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def render_stub(spec: MirrorSpec) -> str:
    assertions_block = ""
    if spec.enforcement_assertions:
        assertions_block = "\n".join([f"- {a}" for a in spec.enforcement_assertions])

    text = f"""📜 {spec.title}

DOCTRINAL MIRROR NOTICE

Source Authority:
Signal Light Press

Canonical Source:
{spec.canonical_source}

Mirror Location:
codex/doctrine_mirror/{spec.mirror_file}

Status:
READ-ONLY MIRROR

Modification Rule:
This file may not be edited independently.
All changes must originate from the Canonical Source.

Enforcement Role:
This mirror exists solely to support enforcement boundaries
and runtime integrity. No canonical body may live here.

{assertions_block}

Violation Notice:
Any divergence from the Canonical Source
constitutes a canonical breach.
"""
    text = "\n".join([line.rstrip() for line in text.splitlines()]).rstrip() + "\n"
    return text


def contains_modal_should(text: str) -> bool:
    return re.search(r"\bshould\b", text, flags=re.IGNORECASE) is not None


def main() -> int:
    # Anchor to signal_light_press/ regardless of invocation directory
    here = Path(__file__).resolve().parents[1]

    mirror_dir = here / "codex" / "doctrine_mirror"
    if not mirror_dir.exists() or not mirror_dir.is_dir():
        print(f"ERROR: mirror dir not found: {mirror_dir}")
        return 2

    backup_dir = (
        here
        / "codex"
        / "_mirror_backups"
        / f"doctrine_mirror_backup_{utc_stamp()}"
    )
    backup_dir.mkdir(parents=True, exist_ok=False)

    specs: list[MirrorSpec] = [
        MirrorSpec(
            mirror_file="BOUNDARY_FIELD_DOCTRINE.md",
            title="BOUNDARY FIELD DOCTRINE",
            canonical_source="codex/doctrine/SYSTEM_BOUNDARIES.md",
            enforcement_assertions=[
                "Boundary fields are enforcement edges, not interpretive interiors.",
                "Mirrors may not contain canonical body content.",
            ],
        ),
        MirrorSpec(
            mirror_file="DOCTRINE_OF_SILENCE_AND_NON_ACTION.md",
            title="DOCTRINE OF SILENCE AND NON-ACTION",
            canonical_source="codex/doctrine/DOCTRINE_OF_SILENCE_AND_NON_ACTION.md",
            enforcement_assertions=[
                "Rhythm OS remains non-agentive; mirrors do not recommend action.",
                "Silence is a valid enforcement outcome.",
            ],
        ),
        MirrorSpec(
            mirror_file="ENERGETIC_PERMISSION_DOCTRINE.md",
            title="ENERGETIC PERMISSION DOCTRINE",
            canonical_source="codex/doctrine/ENERGETIC_PERMISSION_DOCTRINE.md",
            enforcement_assertions=[
                "Energetic permission is descriptive only; it does not authorize action.",
                "Negative permission is informational; no engine may treat it as an error.",
            ],
        ),
        MirrorSpec(
            mirror_file="HUMAN_AUTHORITY_AND_RESPONSIBILITY_DOCTRINE.md",
            title="HUMAN AUTHORITY AND RESPONSIBILITY DOCTRINE",
            canonical_source="codex/doctrine/HUMAN_AUTHORITY_AND_RESPONSIBILITY_DOCTRINE.md",
            enforcement_assertions=[
                "Human judgment remains the sole locus of responsibility.",
                "Mirrors may not issue guidance; they only preserve boundary constraints.",
            ],
        ),
        MirrorSpec(
            mirror_file="RHYTHM_OS_OUTPUT_DOCTRINE.md",
            title="RHYTHM OS OUTPUT DOCTRINE",
            canonical_source="codex/doctrine/RHYTHM_OS_OUTPUT_DOCTRINE.md",
            enforcement_assertions=[
                "Kernel output is descriptive and non-executable.",
                "No mirror may introduce actuation, recommendation, or optimization language.",
            ],
        ),
    ]

    # Backup existing mirrors
    existing = sorted(mirror_dir.glob("*.md"))
    for p in existing:
        shutil.copy2(p, backup_dir / p.name)

    written: list[Path] = []
    for spec in specs:
        out_path = mirror_dir / spec.mirror_file
        content = render_stub(spec)

        if contains_modal_should(content):
            print(f"ERROR: stub contains forbidden modal 'should': {out_path.name}")
            return 3

        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    # Final enforcement scan
    for p in sorted(mirror_dir.glob("*.md")):
        txt = p.read_text(encoding="utf-8", errors="strict")
        if contains_modal_should(txt):
            print(f"ERROR: forbidden modal 'should' remains in mirror: {p.name}")
            return 4

    print("OK: doctrine_mirror rebuilt as enforcement-only stubs.")
    print(f"Backup saved to: {backup_dir}")
    print("Written files:")
    for p in written:
        print(f" - {p.relative_to(here)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
