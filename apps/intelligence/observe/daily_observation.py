from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

# Canonical imports (post-move, no kernel aliasing)


# ------------------------------------------------------------
# CANONICAL ROOT DISCOVERY (NO APP-LAYER COUPLING)
# ------------------------------------------------------------

THIS_DIR = Path(__file__).resolve().parent
WAVE_ROOT = THIS_DIR.parent  # rhythm_os/core/wave
CORE_ROOT = WAVE_ROOT.parent  # rhythm_os/core
RHYTHM_OS_ROOT = CORE_ROOT.parent  # rhythm_os

DATA_DIR = RHYTHM_OS_ROOT / "data"
AUDIT_LOG = DATA_DIR / "audit.log"
RESONANCE_LOG = DATA_DIR / "resonance.log"
POSTURE_DIR = DATA_DIR / "posture"


# ------------------------------------------------------------
# FILESYSTEM HYGIENE
# ------------------------------------------------------------


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# LOGGING (COMMAND-LAYER ONLY)
# ------------------------------------------------------------


def log_audit(message: str) -> None:
    """Append to audit log with timestamp."""
    _ensure_parent(AUDIT_LOG)
    ts = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def log_resonance(domain: str, observation: str, resonance: str) -> None:
    """Log resonance observation (descriptive only)."""
    _ensure_parent(RESONANCE_LOG)
    ts = datetime.now(timezone.utc).isoformat()
    with open(RESONANCE_LOG, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {domain} | {observation} | {resonance}\n")


# ------------------------------------------------------------
# DAILY COMMAND (REFUSAL-FIRST)
# ------------------------------------------------------------


def daily_signal() -> None:
    print("=" * 60)
    print("Rhythm OS — Daily Observation Run")
    print(f"UTC Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("")

    log_audit("Daily run started")

    # --------------------------------------------------------
    # STEP 1 — OPTIONAL HUMAN OBSERVATION
    # --------------------------------------------------------

    print("Step 1: Optional Rhythm Observation")
    print("(Press Enter to skip)")
    domain = input("Domain (Hearth / Sea / Craft / Other): ").strip()

    if domain:
        observation = input("Observed rhythm (brief): ").strip()
        resonance = input("Resonance (present / absent / distorting): ").strip().lower()
        if resonance not in {"present", "absent", "distorting"}:
            resonance = "absent"

        log_resonance(domain, observation, resonance)
        print(f"Logged → {domain} | {observation} | {resonance}")
    else:
        print("No observation logged.")

    # --------------------------------------------------------
    # STEP 2 — POSTURE (EXPLICIT HOLD)
    # --------------------------------------------------------

    print("\nStep 2: Posture")
    print("Posture = HOLD")
    print("Custodial silence maintained.")
    print("No action taken. No inference made.")

    # --------------------------------------------------------
    # STEP 3 — CLOSE
    # --------------------------------------------------------

    log_audit("Daily run complete")
    print("\nDaily run complete.")
    print("All authority remains local and human.")
    print("=" * 60)


# ------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------

if __name__ == "__main__":
    try:
        daily_signal()
    except KeyboardInterrupt:
        print("\nRun interrupted. Silence maintained.")
        log_audit("Daily run interrupted (KeyboardInterrupt)")
    except Exception as e:
        print(f"\nError during daily run: {e}")
        log_audit(f"Error during daily run: {e}")
