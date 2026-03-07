"""
JSONL age-off / data retention janitor.

Prevents unbounded accumulation of daily JSONL files across all dark-field
directories.  The janitor is intentionally passive — it only deletes files
whose names match the ``YYYY-MM-DD.jsonl`` pattern and whose date is older
than the retention window.  It never touches the current day's file.

Usage (standalone):
    python -m rhythm_os.runtime.janitor               # dry-run
    python -m rhythm_os.runtime.janitor --apply       # actually delete

Usage (programmatic):
    from rhythm_os.runtime.janitor import run_janitor
    removed = run_janitor(retain_days=30, apply=True)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Sequence

from rhythm_os.runtime.paths import (
    AUDIT_PATH,
    CONTROL_DIR,
    CONVERGENCE_MEMORY_PATH,
    DOMAIN_DIR,
    GATE_ACTIONS_DIR,
    GATES_DIR,
    HELM_LOG_PATH,
    MARKET_RAW_DIR,
    METERS_DIR,
    NATURAL_DIR,
    OCEAN_RAW_DIR,
    PENSTOCK_DIR,
    PSR_DIR,
    TURBINE_DIR,
    VOICE_LINES_PATH,
)

_DATE_JSONL = re.compile(r"^\d{4}-\d{2}-\d{2}\.jsonl$")

# Directories that rotate daily (one file per day, name = YYYY-MM-DD.jsonl)
_DAILY_DIRS: Sequence[Path] = [
    PENSTOCK_DIR,
    TURBINE_DIR,
    METERS_DIR,
    NATURAL_DIR,
    DOMAIN_DIR,
    CONTROL_DIR,
    MARKET_RAW_DIR,
    OCEAN_RAW_DIR,
    GATES_DIR,
    GATE_ACTIONS_DIR,
    PSR_DIR,
]

DEFAULT_RETAIN_DAYS = 30


def _aged_out(name: str, cutoff: datetime) -> bool:
    """Return True if the file date (from its name) is before the cutoff."""
    if not _DATE_JSONL.match(name):
        return False
    try:
        file_date = datetime.strptime(name[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return file_date < cutoff


def run_janitor(
    retain_days: int = DEFAULT_RETAIN_DAYS,
    apply: bool = False,
    extra_dirs: Sequence[Path] = (),
) -> List[Path]:
    """
    Scan all daily-rotation directories and remove JSONL files older than
    ``retain_days`` days.

    Parameters
    ----------
    retain_days     Files older than this many days are eligible for removal.
    apply           If False (default) the function returns what *would* be
                    removed without deleting anything (dry-run).
    extra_dirs      Additional directories to scan beyond the built-in list.

    Returns
    -------
    List[Path]  Paths that were (or would be) removed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retain_days)
    candidates: List[Path] = []

    dirs = list(_DAILY_DIRS) + list(extra_dirs)
    for directory in dirs:
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_file() and _aged_out(child.name, cutoff):
                candidates.append(child)

    if apply:
        for path in candidates:
            try:
                path.unlink()
            except OSError:
                pass  # best-effort; caller can check what remains

    return candidates


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SignalLogic JSONL janitor")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually delete aged files (default: dry-run)",
    )
    parser.add_argument(
        "--retain-days",
        type=int,
        default=DEFAULT_RETAIN_DAYS,
        metavar="N",
        help=f"Retain files newer than N days (default: {DEFAULT_RETAIN_DAYS})",
    )
    args = parser.parse_args()

    removed = run_janitor(retain_days=args.retain_days, apply=args.apply)
    mode = "Removed" if args.apply else "Would remove"
    print(f"{mode} {len(removed)} file(s):")
    for p in sorted(removed):
        print(f"  {p}")
