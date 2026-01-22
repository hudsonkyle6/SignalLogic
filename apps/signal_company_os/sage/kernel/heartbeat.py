# ================================================================
#  SAGE OS — KERNEL HEARTBEAT (V1.3)
#  Assist Under Discipline
# ================================================================

import os
import sys
import json
import datetime as dt

# ------------------------------------------------
# CANONICAL SAGE ROOT
# ------------------------------------------------
SAGE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if SAGE_ROOT not in sys.path:
    sys.path.insert(0, SAGE_ROOT)

# ------------------------------------------------
# REGISTRY LOADER (SAGE-INTERNAL)
# ------------------------------------------------
try:
    from core.registry_loader import load_registries_or_die
except ImportError as e:
    print(f"❌ Registry loader import failed: {e}")
    raise SystemExit(1)

# ------------------------------------------------
# 1. GOVERNING LAWS CHECK
# ------------------------------------------------
REQUIRED_LAWS = [
    "alignment_law.md",
    "rhythm_law.md",
    "seasonal_law.md",
    "archive_law.md",
    "operator_law.md",
    "boundary_law.md",
    "integrity_law.md",
]

def check_laws():
    laws_path = os.path.join(SAGE_ROOT, "laws")
    return [
        law for law in REQUIRED_LAWS
        if not os.path.exists(os.path.join(laws_path, law))
    ]

# ------------------------------------------------
# 2. DIRECTORY INTEGRITY CHECK
# ------------------------------------------------
REQUIRED_DIRS = [
    "laws",
    "ledger",
    "console",
    "archive",
    "rhythms",
    "oracle_link",
    "shepherd_link",
    "processes",
    "state",
]

def check_directories():
    return [
        d for d in REQUIRED_DIRS
        if not os.path.exists(os.path.join(SAGE_ROOT, d))
    ]

# ------------------------------------------------
# 3. SAGE INTERNAL STATE
# ------------------------------------------------
STATE_FILE = os.path.join(SAGE_ROOT, "state", "sage_state.json")

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"status": None, "last_run": None}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"status": "CORRUPT", "last_run": None}

def write_state():
    state = {
        "status": "OK",
        "last_run": dt.datetime.now(dt.UTC).isoformat()
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

# ------------------------------------------------
# 4. HEARTBEAT
# ------------------------------------------------
def heartbeat():
    today = dt.date.today().isoformat()

    print("\n══════════════════════════════════════")
    print("        SAGE OS — KERNEL HEARTBEAT")
    print("══════════════════════════════════════")
    print(f" Date: {today}")
    print(f" Root: {SAGE_ROOT}\n")

    # Laws
    missing_laws = check_laws()
    if missing_laws:
        print("❌ Missing Governing Laws:")
        for law in missing_laws:
            print(f"  - {law}")
        return False
    else:
        print("✓ All governing laws present")

    # Directories
    missing_dirs = check_directories()
    if missing_dirs:
        print("\n❌ Missing Required Directories:")
        for d in missing_dirs:
            print(f"  - {d}")
        return False
    else:
        print("✓ Directory structure intact")

    # Registry integrity
    print("\nRegistry Integrity:")
    try:
        registries = load_registries_or_die()
        _ = registries.get("sage")
        print("✓ Sage registry loaded and frozen")
    except Exception as e:
        print(f"❌ Registry failure: {e}")
        return False

    # State
    state = load_state()
    print("\nSage Internal State:")
    print(f"  Status:   {state.get('status')}")
    print(f"  LastRun:  {state.get('last_run')}")

    write_state()

    print("\n✓ Kernel integrity verified")
    print("✓ Registries verified and immutable")
    print("✓ Sage authorized to observe and report")
    print("══════════════════════════════════════\n")

    return True

# ------------------------------------------------
# ENTRY POINT
# ------------------------------------------------
if __name__ == "__main__":
    raise SystemExit(0 if heartbeat() else 1)
