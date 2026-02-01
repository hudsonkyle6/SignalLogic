from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

REPO_ROOT = Path(__file__).resolve()
# If you place this under signal_light_press/tools/, repo root is 2 parents up.
# Adjust if you place it elsewhere.
for _ in range(4):
    if (REPO_ROOT / ".git").exists():
        break
    REPO_ROOT = REPO_ROOT.parent

SLP_ROOT = REPO_ROOT / "signal_light_press"
AUDIT_REPORT = SLP_ROOT / "fieldnotes" / "audits" / "AUDIT_HEADERS_REPORT.md"

# File types we will attempt to govern
GOVERNABLE_SUFFIXES = {
    ".md", ".txt",
    ".yaml", ".yml",
}

HEADER_START_RE = re.compile(r"^\s*Authority:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

# We treat the "SLP header" as a simple key/value block at the very top.
# This matches the style you’ve been using (Authority / Classification / Status / etc.).
REQUIRED_KEYS = [
    "Authority",
    "Classification",
    "Status",
    "Domain",
    "Applies To",
    "Amendment Rule",
    "Executable",
]

# Conservative, governance-safe enums (avoid claiming CANONICAL unless you mean it).
# You can tighten these later after the commit lands.
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
    Directory-based policy. This is the single source of truth for this fixing pass.
    Adjust mapping here if your contract expects different labels.
    """
    rel = p.relative_to(REPO_ROOT).as_posix()

    # Hard archive zones
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

    # Authoritative roots called out by your hook
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

    # Default: governed but not canon-claimed
    return HeaderProfile(
        classification=DEFAULTS_LIVE["Classification"],
        status=DEFAULTS_LIVE["Status"],
        domain="Document",
        applies_to="Signal Light Press",
        amendment_rule="Signal Light Press only",
    )

def extract_paths_from_audit(report_path: Path) -> list[Path]:
    """
    Extract any Windows or posix-looking paths that point inside signal_light_press.
    Works even if the report format changes.
    """
    if not report_path.exists():
        return []

    text = report_path.read_text(encoding="utf-8", errors="ignore")

    # Capture both:
    # - C:/Users/.../SignalLogic/signal_light_press/...
    # - signal_light_press/...
    candidates = set()

    # Windows absolute paths
    win_re = re.compile(r"([A-Za-z]:[\\/][^\s<>\"']*?signal_light_press[\\/][^\s<>\"']+)")
    for m in win_re.finditer(text):
        raw = m.group(1).replace("\\", "/")
        idx = raw.lower().find("signal_light_press/")
        if idx >= 0:
            rel = raw[idx:]
            candidates.add((REPO_ROOT / rel).resolve())

    # Relative repo paths
    rel_re = re.compile(r"(signal_light_press[\\/][^\s<>\"']+)")
    for m in rel_re.finditer(text):
        raw = m.group(1).replace("\\", "/")
        candidates.add((REPO_ROOT / raw).resolve())

    paths = []
    for p in candidates:
        try:
            # Keep only files under repo root
            p.relative_to(REPO_ROOT)
            if p.is_file():
                paths.append(p)
        except Exception:
            continue

    return sorted(set(paths))

def scan_signal_light_press() -> list[Path]:
    paths: list[Path] = []
    if not SLP_ROOT.exists():
        return paths
    for p in SLP_ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in GOVERNABLE_SUFFIXES:
            paths.append(p)
    return paths

def has_header_block(text: str) -> bool:
    # We assume header exists if "Authority:" is found near the top (first ~80 lines)
    head = "\n".join(text.splitlines()[:80])
    return bool(HEADER_START_RE.search(head))

def parse_header_block(text: str) -> Tuple[dict[str, str], int]:
    """
    Parse a key/value header block at the top.
    Returns (header_dict, end_line_index_exclusive).
    If parsing fails, returns ({}, 0).
    """
    lines = text.splitlines()
    header: dict[str, str] = {}
    end = 0

    # Only parse if header starts at top within first 5 lines
    top_chunk = "\n".join(lines[:10])
    if not re.search(r"^\s*Authority:\s*", top_chunk, re.IGNORECASE | re.MULTILINE):
        return {}, 0

    # Read until first blank line AFTER we have seen at least Authority
    seen_any = False
    for i, line in enumerate(lines):
        if line.strip() == "":
            if seen_any:
                end = i + 1  # include the blank line separator
                break
            else:
                continue

        m = re.match(r"^\s*([A-Za-z][A-Za-z \-&]+)\s*:\s*(.*?)\s*$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            header[key] = val
            if key.lower() == "authority":
                seen_any = True
        else:
            # Non key/value line encountered — treat as end of header if we already started
            if seen_any:
                end = i
            break

    return header, end

def render_header(profile: HeaderProfile) -> str:
    # Exact key casing to match REQUIRED_KEYS
    header = {
        "Authority": profile.authority,
        "Classification": profile.classification,
        "Status": profile.status,
        "Domain": profile.domain,
        "Applies To": profile.applies_to,
        "Amendment Rule": profile.amendment_rule,
        "Executable": profile.executable,
    }
    # Preserve a clean, minimal header: key: value lines + blank line.
    out = []
    for k in REQUIRED_KEYS:
        out.append(f"{k}: {header[k]}")
    out.append("")  # blank line separator
    return "\n".join(out)

def normalize_or_insert_header(path: Path) -> Optional[str]:
    """
    Returns:
      - "inserted" / "normalized" if changes were made
      - None if no changes
    """
    original = path.read_text(encoding="utf-8", errors="ignore")
    profile = profile_for_path(path)
    desired = render_header(profile)

    if not has_header_block(original):
        # Insert header at very top
        new_text = desired + original.lstrip("\ufeff")  # strip BOM if present
        if new_text != original:
            path.write_text(new_text, encoding="utf-8", newline="\n")
            return "inserted"
        return None

    existing_header, end_idx = parse_header_block(original)
    # If header exists but we couldn’t parse it safely, we’ll replace the top block up to first blank line.
    if end_idx == 0:
        # Replace first ~25 lines until first blank line
        lines = original.splitlines()
        cut = 0
        for i, line in enumerate(lines[:200]):
            if line.strip() == "":
                cut = i + 1
                break
        new_text = desired + "\n".join(lines[cut:]) + ("\n" if original.endswith("\n") else "")
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return "normalized"

    # Merge: keep any extra header keys you might have, but enforce required keys to desired values
    merged = dict(existing_header)
    desired_dict, _ = parse_header_block(desired + "\nX")  # cheap parse trick
    for k in REQUIRED_KEYS:
        merged[k] = desired_dict.get(k, merged.get(k, ""))

    # Render merged in REQUIRED_KEYS order, then append any extra keys (stable order)
    extras = [k for k in merged.keys() if k not in REQUIRED_KEYS]
    extras_sorted = sorted(extras, key=lambda s: s.lower())

    out_lines = []
    for k in REQUIRED_KEYS:
        out_lines.append(f"{k}: {merged[k]}")
    for k in extras_sorted:
        out_lines.append(f"{k}: {merged[k]}")
    out_lines.append("")

    new_header = "\n".join(out_lines)
    remainder = "\n".join(original.splitlines()[end_idx:])

    new_text = new_header + remainder.lstrip("\n")
    if new_text != original:
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return "normalized"
    return None

def main() -> int:
    if not SLP_ROOT.exists():
        print(f"[fix_headers] ERROR: {SLP_ROOT} not found (run from repo root).")
        return 2

    targets = extract_paths_from_audit(AUDIT_REPORT)
    source = "audit report"
    if not targets:
        targets = scan_signal_light_press()
        source = "scan"

    changed_inserted = 0
    changed_normalized = 0
    untouched = 0
    skipped = 0

    print(f"[fix_headers] Targets from {source}: {len(targets)} files")

    for p in targets:
        if p.suffix.lower() not in GOVERNABLE_SUFFIXES:
            skipped += 1
            continue
        try:
            result = normalize_or_insert_header(p)
            if result == "inserted":
                changed_inserted += 1
            elif result == "normalized":
                changed_normalized += 1
            else:
                untouched += 1
        except Exception as e:
            print(f"[fix_headers] ERROR on {p}: {e}")
            return 3

    print("[fix_headers] Done.")
    print(f"  inserted:   {changed_inserted}")
    print(f"  normalized: {changed_normalized}")
    print(f"  untouched:  {untouched}")
    print(f"  skipped:    {skipped}")
    print("")
    print("[fix_headers] Next: rerun your header audit / re-attempt commit.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
