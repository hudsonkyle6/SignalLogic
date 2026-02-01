#fix_headers.py
from __future__ import annotations

import re
import sys
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# ──────────────────────────────────────────────────────────────
# Repo discovery
# ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve()
for _ in range(6):
    if (REPO_ROOT / ".git").exists():
        break
    REPO_ROOT = REPO_ROOT.parent

SLP_ROOT = REPO_ROOT / "signal_light_press"

GOVERNABLE_SUFFIXES = {".md", ".txt", ".yaml", ".yml"}

# ──────────────────────────────────────────────────────────────
# Header + seal constants
# ──────────────────────────────────────────────────────────────

REQUIRED_KEYS = [
    "Authority",
    "Classification",
    "Status",
    "Domain",
    "Applies To",
    "Amendment Rule",
    "Executable",
]

HEADER_START_RE = re.compile(r"^\s*Authority:\s*", re.IGNORECASE)

SEAL_CLOSING = "— END OF DOCUMENT —"
SEAL_ACTUAL_PREFIX = "SEAL:"

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def is_archive_path(path: Path) -> bool:
    p = path.as_posix()
    return p.startswith("signal_light_press/archive/") or "/archive/" in p

# ──────────────────────────────────────────────────────────────
# Header profiles
# ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HeaderProfile:
    authority: str
    classification: str
    status: str
    domain: str
    applies_to: str
    amendment_rule: str
    executable: str = "No"


def profile_for_path(p: Path) -> HeaderProfile:
    rel = p.relative_to(REPO_ROOT).as_posix()

    if rel.startswith("signal_light_press/fieldnotes/"):
        return HeaderProfile(
            "Signal Light Press", "ARCHIVE", "ARCHIVED",
            "Fieldnotes", "Signal Light Press (Internal)",
            "Signal Light Press only",
        )

    if "/archive/" in rel:
        return HeaderProfile(
            "Signal Light Press", "ARCHIVE", "ARCHIVED",
            "Archive", "Signal Light Press (Internal)",
            "Signal Light Press only",
        )

    if rel.startswith("signal_light_press/codex/"):
        return HeaderProfile(
            "Signal Light Press", "CROWN JEWEL", "CANONICAL",
            "Codex", "Signal Light Press",
            "Signal Light Press only",
        )

    if rel.startswith("signal_light_press/doctrine"):
        return HeaderProfile(
            "Signal Light Press", "CROWN JEWEL", "CANONICAL",
            "Doctrine", "Signal Light Press",
            "Signal Light Press only",
        )

    return HeaderProfile(
        "Signal Light Press", "WORKING", "DRAFT",
        "Document", "Signal Light Press",
        "Signal Light Press only",
    )

# ──────────────────────────────────────────────────────────────
# Header parsing / rendering
# ──────────────────────────────────────────────────────────────

def parse_header(text: str) -> Tuple[dict[str, str], int]:
    lines = text.splitlines()
    header: dict[str, str] = {}
    end = 0

    if not lines or not HEADER_START_RE.match(lines[0]):
        return {}, 0

    for i, line in enumerate(lines):
        if not line.strip():
            end = i + 1
            break
        m = re.match(r"^\s*([A-Za-z \-]+):\s*(.*?)\s*$", line)
        if not m:
            break
        header[m.group(1)] = m.group(2)

    return header, end


def render_header(profile: HeaderProfile) -> str:
    lines = [
        f"Authority: {profile.authority}",
        f"Classification: {profile.classification}",
        f"Status: {profile.status}",
        f"Domain: {profile.domain}",
        f"Applies To: {profile.applies_to}",
        f"Amendment Rule: {profile.amendment_rule}",
        f"Executable: {profile.executable}",
        "",
    ]
    return "\n".join(lines)

# ──────────────────────────────────────────────────────────────
# Seals
# ──────────────────────────────────────────────────────────────

def compute_actual_seal(body: str) -> str:
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"{SEAL_ACTUAL_PREFIX} {h}"


def split_body_and_seals(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    lines = text.rstrip().splitlines()
    closing = actual = None

    if lines and lines[-1].startswith(SEAL_ACTUAL_PREFIX):
        actual = lines.pop()

    if lines and lines[-1] == SEAL_CLOSING:
        closing = lines.pop()

    return "\n".join(lines) + "\n", closing, actual

# ──────────────────────────────────────────────────────────────
# Core fixer
# ──────────────────────────────────────────────────────────────

def fix_file(path: Path) -> bool:
    if is_archive_path(path):
        return False

    original = path.read_text(encoding="utf-8", errors="ignore")
    profile = profile_for_path(path)

    _, header_end = parse_header(original)
    body = original.splitlines()[header_end:] if header_end else original.splitlines()
    body_text, _, _ = split_body_and_seals("\n".join(body))

    rendered_header = render_header(profile)
    actual_seal = compute_actual_seal(body_text)

    new_text = (
        rendered_header +
        body_text.rstrip() + "\n\n" +
        SEAL_CLOSING + "\n" +
        actual_seal + "\n"
    )

    if new_text != original:
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return True

    return False

# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main() -> int:
    if not SLP_ROOT.exists():
        print("[fix] signal_light_press not found")
        return 2

    changed = 0
    total = 0

    for p in SLP_ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in GOVERNABLE_SUFFIXES:
            total += 1
            if fix_file(p):
                changed += 1

    print(f"[fix] scanned: {total}")
    print(f"[fix] modified: {changed}")
    print("[fix] headers + seals canonicalized")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
