# ================================================================
#  SAGE OS — DAILY REPORT
#  Canonical, read-only historical record
# ================================================================

import json
import csv
import os
import datetime
from pathlib import Path

# ------------------------------------------------
# ROOT CONFIGURATION
# ------------------------------------------------
ROOT = Path(r"C:\Users\SignalADmin\Signal Archive\SignalLogic\rhythm_os\sage")

ARCHIVE_LOGS = ROOT / "archive" / "logs"
DOCTRINE_DIR = ROOT / "archive" / "doctrine"
STATE_FILE = ROOT / "state" / "sage_state.json"
MIRRORS_DIR = ROOT / "rhythms" / "mirrors"

# ------------------------------------------------
# INPUT RESOLUTION (FROZEN DAY ONLY)
# ------------------------------------------------
def resolve_snapshot():
    snapshots = sorted(MIRRORS_DIR.glob("oracle_snapshot_*.csv"))
    if not snapshots:
        raise FileNotFoundError("No frozen oracle snapshot found.")
    return snapshots[-1]  # most recent frozen snapshot


# ------------------------------------------------
# LOADERS (READ-ONLY)
# ------------------------------------------------
def load_oracle_snapshot(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError("Oracle snapshot is empty.")
    return rows[-1]  # single-day snapshot


def load_sage_state():
    if not STATE_FILE.exists():
        return {"status": "UNKNOWN", "last_run": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_doctrine_titles():
    titles = []
    for md in sorted(DOCTRINE_DIR.glob("*.md")):
        titles.append(md.name)
    return titles


# ------------------------------------------------
# REPORT WRITER
# ------------------------------------------------
def write_report(snapshot, sage_state, doctrine_files, snapshot_path):
    date = snapshot.get("Date") or snapshot.get("date")
    today = datetime.date.today().isoformat()

    filename = f"DAILY_REPORT_{today}.md"
    report_path = ARCHIVE_LOGS / filename

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# DAILY REPORT — SAGE OS\n\n")

        f.write(f"**Report Date:** {today}\n")
        f.write(f"**Oracle Snapshot:** {snapshot_path.name}\n")
        f.write("**Mode:** Assist Under Discipline\n\n")

        f.write("## System Authorization\n")
        f.write(f"- Sage Status: {sage_state.get('status')}\n")
        f.write(f"- Last Kernel Heartbeat: {sage_state.get('last_run')}\n\n")

        f.write("## Observed World State (Frozen)\n")
        for key in [
            "Season", "SignalState", "ResonanceValue", "Amplitude",
            "Phase", "Change", "Streak", "A_t", "C_t", "E_t", "H_t",
            "DarkFieldBand", "D_t"
        ]:
            if key in snapshot:
                f.write(f"- {key}: {snapshot[key]}\n")

        f.write("\n## Doctrine Referenced\n")
        for d in doctrine_files:
            f.write(f"- {d}\n")

        f.write("\n## Interpretation Boundary\n")
        f.write(
            "This report records observed and authorized state only.\n"
            "It does not predict, recommend, or authorize action.\n"
            "Meaning, posture, and action remain governed elsewhere.\n"
        )

        f.write("\n---\n")
        f.write("© Signal Light Press\n")

    return report_path


# ------------------------------------------------
# MAIN
# ------------------------------------------------
def main():
    ARCHIVE_LOGS.mkdir(parents=True, exist_ok=True)

    snapshot_path = resolve_snapshot()
    snapshot = load_oracle_snapshot(snapshot_path)
    sage_state = load_sage_state()
    doctrine_files = load_doctrine_titles()

    report_path = write_report(
        snapshot=snapshot,
        sage_state=sage_state,
        doctrine_files=doctrine_files,
        snapshot_path=snapshot_path
    )

    print("\n══════════════════════════════════════")
    print("        SAGE OS — DAILY REPORT")
    print("══════════════════════════════════════")
    print(f" Report written: {report_path}")
    print(" Scope: Frozen snapshot only")
    print(" Authority: Assist Under Discipline")
    print("══════════════════════════════════════\n")


if __name__ == "__main__":
    main()
