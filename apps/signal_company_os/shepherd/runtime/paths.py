"""
Shepherd Runtime — Canonical Paths
Authority: Signal Light Press
Classification: Protected Internal

Defines WHERE Shepherd is allowed to look.
No discovery. No scanning. No inference.
"""

from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parents[3]

ROOT = project_root()

# ---- READ-ONLY INPUTS ----

# ---- READ-ONLY INPUTS (CANONICAL) ----

# Oracle publishes snapshots via Sage-controlled handoff
ORACLE_SNAPSHOT = (
    ROOT
    / "rhythm_os"
    / "sage"
    / "oracle_link"
    / "oracle_snapshot.json"
)

SAGE_STATE = (
    ROOT
    / "rhythm_os"
    / "sage"
    / "state"
    / "sage_state.json"
)

SHEPHERD_LAW = (
    ROOT
    / "rhythm_os"
    / "shepherd"
    / "state"
    / "shepherd_state.yaml"
)

# ---- FUTURE WRITE TARGET (NOT USED YET) ----
SHEPHERD_POSTURE_SNAPSHOT = (
    ROOT
    / "rhythm_os"
    / "shepherd"
    / "state"
    / "shepherd_posture_snapshot.yaml"
)


# ---- FUTURE WRITE TARGET (not used yet) ----
SHEPHERD_POSTURE_SNAPSHOT = (
    ROOT / "rhythm_os" / "shepherd" / "state" / "shepherd_posture_snapshot.yaml"
)
