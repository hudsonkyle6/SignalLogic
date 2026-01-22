"""
Shepherd Runtime — Skeleton v0.1 (Posture Engine Only)

- Reads: Oracle snapshot (read-only)
- Reads: Sage state (read-only)
- Reads: Shepherd law (shepherd_state.yaml)
- Writes: shepherd_posture_snapshot.yaml (later steps)

NO allocation. NO optimization. NO execution directives.
Fail-closed by design.
"""

from __future__ import annotations

from pathlib import Path
import sys
import json

from pathlib import Path
from rhythm_os.shepherd.runtime import paths, loaders
from .read_sage import read_latest_sage_posture

from rhythm_os.shepherd.runtime import paths, loaders, readiness
from rhythm_os.shepherd.runtime.readiness import InputStatus

def main() -> int:
    print("🐑 Shepherd Runtime v0.3 — readiness check")

    oracle_status = readiness.assess_json_readiness(paths.ORACLE_SNAPSHOT)

    if oracle_status != InputStatus.READY:
        print(f"Shepherd posture: DORMANT (Oracle = {oracle_status})")
        print("Reason: Required upstream signal not yet published.")
        return 0

    # Only now is loading permitted
    oracle = loaders.load_json(paths.ORACLE_SNAPSHOT)
    sage   = loaders.load_json(paths.SAGE_STATE)
    law    = loaders.load_yaml(paths.SHEPHERD_LAW)

    print("✓ Oracle snapshot loaded")
    print("✓ Sage state loaded")
    print("✓ Shepherd law loaded")

    print("Shepherd posture: HOLD (logic not installed)")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
