#fix_headers_and_seals
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# -----------------------------------------------------------------------------
# REPO ROOT DISCOVERY
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve()
for _ in range(6):
    if (REPO_ROOT / ".git").exists():
        break
    REPO_ROOT = REPO_ROOT.parent

SLP_ROOT = REPO_ROOT / "signal_light_press"
AUDIT_REPORT = SLP_ROOT / "fieldnotes" / "audits" / "AUDIT_HEADERS_REPORT.md"

# -----------------------------------------------------------------------------
# INTENT
# -----------------------------------------------------------------------------
# This tool performs MINIMUM header normalization only.
#
# It intentionally:
# - inserts missing headers
# - normalizes required header keys and ordering
#
# It explicitly does NOT:
# - add Scope
# - add Effective Date
# - add closing seals
# - add actual seals
# - upgrade legacy canon
#
# Legacy canon is handled by policy exemptions, not mutation.
# Governance enforcement belongs to enforce_headers.py only.
# -----------------------------------------------------------------------------

# File types we will attempt to govern
GOVERNABLE_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}

HEADER_START_RE = re.compile(
    r"^\s*Authority:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

REQUIRED_KEYS = [
    "Authority",
    "Classification",
    "Status",
    "Domain",
    "Applies To",
    "Amendment Rule",
    "Executable",
]

DEFAULTS_CANON = {
    "Authority": "Signal Light Press",
    "Classification": "CROWN JEWEL",
    "Status": "CANONICAL",
    "Executable": "No",
}

DEFAULTS_LIVE = {
    "Authority": "Signal Light Press",
    "Classification": "WORKING",
    "Status": "DRAFT",
    "Executable": "No",
}

DEFAULTS_ARCHIVE = {
    "Authority": "Signal Light Press",
    "Classification": "ARCHIVE",
    "Status": "ARCHIVED",
    "Executable": "No",
}

# -----------------------------------------------------------------------------
# HEADER PROFILE
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class HeaderProfile:
    classification: str
    status: str
    domain: str
    applies_to: str
    amendment_rule: str
    executable: str = "No"
    authority: str = "Signal Light Press"


def profile_for_path(p: Path) -> HeaderProfile:
    """
    Directory-based policy.
    This is the single source of truth for this fixing pass.
    """
    rel = p.relative_to(REPO_ROOT).as_posix()

    if rel.startswith("signal_light_press/fieldnotes/"):
        return HeaderProfile(
            classification=DEFAULTS_ARCHIVE["Classification"],
            status=DEFAULTS_ARCHIVE["Status"],
            domain="Fieldnotes",
            applies_to="Signal Light Press (Internal)",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/archive/") or "/archive/" in rel:
        return HeaderProfile(
            classification=DEFAULTS_ARCHIVE["Classification"],
            status=DEFAULTS_ARCHIVE["Status"],
            domain="Archive",
            applies_to="Signal Light Press (Internal)",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/codex/"):
        return HeaderProfile(
            classification=DEFAULTS_CANON["Classification"],
            status=DEFAULTS_CANON["Status"],
            domain="Codex",
            applies_to="Signal Light Press",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/contracts/"):
        return HeaderProfile(
            classification=DEFAULTS_CANON["Classification"],
            status=DEFAULTS_CANON["Status"],
            domain="Contract",
            applies_to="Signal Light Press",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/registers/"):
        return HeaderProfile(
            classification=DEFAULTS_CANON["Classification"],
            status=DEFAULTS_CANON["Status"],
            domain="Register",
            applies_to="Signal Light Press",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/manifests/"):
        return HeaderProfile(
            classification=DEFAULTS_LIVE["Classification"],
            status=DEFAULTS_LIVE["Status"],
            domain="Manifest",
            applies_to="Signal Light Press",
            amendment_rule="Signal Light Press only",
        )

    if rel.startswith("signal_light_press/editions/"):
        return HeaderProfile(
            classification=DEFAULTS_LIVE["Classification"],
            status=DEFAULTS_LIVE["Status"],
            domain="Edition",
            applies_to="Signal Light Press",
            amendment_rule="Signal Light Press only",
        )

    return HeaderProfile(
        classification=DEFAULTS_LIVE["Classification"],
        status=DEFAULTS_LIVE["Status"],
        domain="Document",
        applies_to="Signal Light Press",
        amendment_rule="Signal Light Press only",
    )


# -----------------------------------------------------------------------------
# TARGET DISCOVERY
# -----------------------------------------------------------------------------
def extract_paths_from_audit(report_path: Path) -> list[Path]:
    if not report_path.exists():
        return []

    text = report_path.read_text(encoding="utf-8", errors="ignore")
    candidates: set[Path] = set()

    win_re = re.compile(r"([A-Za-z]:[\\/].*?signal_light_press[\\/][^\s<>\"']+)")
    for m in win_re.finditer(text):
        raw = m.group(1).replace("\\", "/")
        idx = raw.lower().find("signal_light_press/")
        if idx >= 0:
            candidates.add((REPO_ROOT / raw[idx:]).resolve())

    rel_re = re.compile(r"(signal_light_press[\\/][^\s<>\"']+)")
    for m in rel_re.finditer(text):
        candidates.add((REPO_ROOT / m.group(1).replace("\\", "/")).resolve())

    paths = []
    for p in candidates:
        try:
            p.relative_to(REPO_ROOT)
            if p.is_file():
                paths.append(p)
        except Exception:
            pass

    return sorted(set(paths))


def scan_signal_light_press() -> list[Path]:
    if not SLP_ROOT.exists():
        return []
    return [
        p
        for p in SLP_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in GOVERNABLE_SUFFIXES
    ]


# -----------------------------------------------------------------------------
# HEADER PARSING
# -----------------------------------------------------------------------------
def has_header_block(text: str) -> bool:
    head = "\n".join(text.splitlines()[:80])
    return bool(HEADER_START_RE.search(head))


def parse_header_block(text: str) -> Tuple[dict[str, str], int]:
    lines = text.splitlines()
    header: dict[str, str] = {}
    end = 0

    top = "\n".join(lines[:10])
    if not re.search(r"^\s*Authority:\s*", top, re.IGNORECASE | re.MULTILINE):
        return {}, 0

    seen = False
    for i, line in enumerate(lines):
        if not line.strip():
            if seen:
                end = i + 1
                break
            continue

        m = re.match(r"^\s*([A-Za-z][A-Za-z \-&]+)\s*:\s*(.*?)\s*$", line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            header[key] = val
            if key.lower() == "authority":
                seen = True
        else:
            if seen:
                end = i
            break

    return header, end


def render_header(profile: HeaderProfile) -> str:
    header = {
        "Authority": profile.authority,
        "Classification": profile.classification,
        "Status": profile.status,
        "Domain": profile.domain,
        "Applies To": profile.applies_to,
        "Amendment Rule": profile.amendment_rule,
        "Executable": profile.executable,
    }

    lines = [f"{k}: {header[k]}" for k in REQUIRED_KEYS]
    lines.append("")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# NORMALIZATION
# -----------------------------------------------------------------------------
def normalize_or_insert_header(path: Path) -> Optional[str]:

def apply_seals(path: Path) -> None:
    if is_archive_path(path):
        return
    # TODO: canonical closing + actual seal logic

    original = path.read_text(encoding="utf-8", errors="ignore")
    profile = profile_for_path(path)
    desired = render_header(profile)

    if not has_header_block(original):
        new_text = desired + original.lstrip("\ufeff")
        if new_text != original:
            path.write_text(new_text, encoding="utf-8", newline="\n")
            return "inserted"
        return None

    existing, end_idx = parse_header_block(original)
    if end_idx == 0:
        lines = original.splitlines()
        cut = next((i + 1 for i, l in enumerate(lines[:200]) if not l.strip()), 0)
        new_text = desired + "\n".join(lines[cut:])
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return "normalized"

    merged = dict(existing)
    desired_dict, _ = parse_header_block(desired + "\nX")
    for k in REQUIRED_KEYS:
        merged[k] = desired_dict.get(k, merged.get(k, ""))

    extras = sorted(k for k in merged if k not in REQUIRED_KEYS)
    out = [f"{k}: {merged[k]}" for k in REQUIRED_KEYS]
    out += [f"{k}: {merged[k]}" for k in extras]
    out.append("")

    remainder = "\n".join(original.splitlines()[end_idx:])
    new_text = "\n".join(out) + remainder.lstrip("\n")

    if new_text != original:
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return "normalized"

    return None


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main() -> int:
    if not SLP_ROOT.exists():
        print("[fix_headers] ERROR: signal_light_press not found.")
        return 2

    targets = extract_paths_from_audit(AUDIT_REPORT)
    source = "audit report"
    if not targets:
        targets = scan_signal_light_press()
        source = "scan"

    ins = norm = ok = skip = 0
    print(f"[fix_headers] Targets from {source}: {len(targets)}")

    for p in targets:
        if p.suffix.lower() not in GOVERNABLE_SUFFIXES:
            skip += 1
            continue
        try:
            r = normalize_or_insert_header(p)
            if r == "inserted":
                ins += 1
            elif r == "normalized":
                norm += 1
            else:
                ok += 1
        except Exception as e:
            print(f"[fix_headers] ERROR {p}: {e}")
            return 3

    print("[fix_headers] Done.")
    print(f"  inserted:   {ins}")
    print(f"  normalized: {norm}")
    print(f"  untouched:  {ok}")
    print(f"  skipped:    {skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
