"""
SAGE OS — MORNING BRIEF
Mode: Assist Under Discipline
Authority: Signal Light Press
Executable: Yes (Narrative Only)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# -------------------------------------------------
# KERNEL HEARTBEAT GATE
# -------------------------------------------------

STATE_FILE = Path(__file__).resolve().parents[1] / "state" / "sage_state.json"
MAX_AGE_SECONDS = 60 * 60 * 24  # 24 hours

def require_kernel_integrity():
    if not STATE_FILE.exists():
        print("❌ Kernel state missing. Sage will not speak.")
        sys.exit(1)

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except Exception:
        print("❌ Kernel state unreadable. Sage will not speak.")
        sys.exit(1)

    if state.get("status") != "OK":
        print("❌ Kernel status not OK. Sage will not speak.")
        sys.exit(1)

    last_run = state.get("last_run")
    if not last_run:
        print("❌ Kernel timestamp missing. Sage will not speak.")
        sys.exit(1)

    ts = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - ts).total_seconds()

    if age > MAX_AGE_SECONDS:
        print("❌ Kernel heartbeat stale. Sage will not speak.")
        sys.exit(1)

# -------------------------------------------------
# SNAPSHOT DISCOVERY (READ-ONLY, FROZEN)
# -------------------------------------------------

ARCHIVE_DIR = Path(__file__).resolve().parents[1] / "archive" / "snapshots"

def get_latest_snapshot():
    snapshots = list(ARCHIVE_DIR.glob("signal_*.csv"))

    if not snapshots:
        print("❌ No frozen oracle snapshots found. Sage remains silent.")
        sys.exit(1)

    def extract_date(p):
        try:
            return datetime.strptime(
                p.stem.replace("signal_", ""),
                "%Y-%m-%d"
            )
        except ValueError:
            return datetime.min

    snapshots.sort(key=extract_date)
    latest = snapshots[-1]
    anchor_date = extract_date(latest).date().isoformat()
    return latest, anchor_date

# -------------------------------------------------
# NARRATIVE POSTURE CLASSIFICATION (SAFE)
# -------------------------------------------------

def classify_posture(snapshot_path):
    """
    Narrative-only posture classification.
    No prescriptions. No thresholds imply action.
    Fails closed to STABILITY.
    """

    posture = "STABILITY"

    try:
        content = snapshot_path.read_text().lower()

        if "drift" in content and "rising" in content:
            posture = "ACCUMULATION"

        if "margin" in content or "edge" in content:
            posture = "MARGINAL_OBSERVATION"

    except Exception:
        posture = "STABILITY"

    return posture

# -------------------------------------------------
# MORNING BRIEF
# -------------------------------------------------

def morning_brief():
    require_kernel_integrity()

    snapshot, anchor_date = get_latest_snapshot()
    posture = classify_posture(snapshot)

    print("────────────────────────────────────────")
    print("        🌅 SAGE OS — MORNING BRIEF")
    print("────────────────────────────────────────")
    print(f" Anchor Day: {anchor_date}")
    print(" Authority:  Frozen Oracle Snapshot")
    print(" Mode:       Assist Under Discipline")
    print("────────────────────────────────────────")
    print("")

    if posture == "STABILITY":
        print("WORLD CONTEXT")
        print("• Conditions remain coherent and stable.")
        print("• Momentum is consolidating, not opening.")
        print("• No marginal instability detected.")
        print("")
        print("POSTURE")
        print("• Stability favors maintenance over movement.")
        print("• Observation remains sufficient.")
        print("")
        print("CONSTRAINTS")
        print("• Do not force momentum.")
        print("• Do not escalate commitments.")
        print("")

    elif posture == "MARGINAL_OBSERVATION":
        print("WORLD CONTEXT")
        print("• Core conditions remain stable.")
        print("• Margins show asymmetry or early disturbance.")
        print("• No center-line fracture detected.")
        print("")
        print("POSTURE")
        print("• Attention to edges is warranted.")
        print("• Observation may shift laterally without commitment.")
        print("")
        print("CONSTRAINTS")
        print("• No pursuit is implied.")
        print("• No commitment is authorized.")
        print("")

    elif posture == "ACCUMULATION":
        print("WORLD CONTEXT")
        print("• External conditions appear quiet.")
        print("• Internal or latent pressure may be accumulating.")
        print("• Release conditions are not yet legible.")
        print("")
        print("POSTURE")
        print("• Waiting performs an active function.")
        print("• Action now would disperse energy.")
        print("")
        print("CONSTRAINTS")
        print("• Avoid premature motion.")
        print("• Preserve optionality.")
        print("")

    print("CLOSING NOTE")
    print("• Sage describes conditions, not decisions.")
    print("• Action remains human.")
    print("• SageOS is present to assist.")
    print("────────────────────────────────────────")

# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------

if __name__ == "__main__":
    morning_brief()

