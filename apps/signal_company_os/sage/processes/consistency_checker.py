"""
consistency_checker.py

SageOS Consistency Checker

Run from SageOS root:
    python -m processes.consistency_checker
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from registry_loader import load_registry, resolve_path  # type: ignore


def check_paths(reg: dict) -> list[str]:
    errors: list[str] = []

    # Check root
    root_path = Path(reg["paths"]["root"])
    if not root_path.exists():
        errors.append(f"[PATH] Root path does not exist: {root_path}")

    # Check each category path
    for key, val in reg["paths"].items():
        p = Path(val)
        if not p.exists():
            errors.append(f"[PATH] Directory missing for '{key}': {p}")

    return errors


def check_files_exist(reg: dict) -> list[str]:
    errors: list[str] = []

    for category, mapping in reg["files"].items():
        for key in mapping:
            p = resolve_path(reg, category, key)
            if not p.exists():
                # Some may be intentionally missing and created at runtime (e.g. rhythms),
                # so mark as WARN rather than error.
                errors.append(f"[WARN] File missing (will be created on demand): {p}")

    return errors


def check_csv_headers(reg: dict) -> list[str]:
    errors: list[str] = []

    # Expected schemas (must match sage_hst.py)
    expected = {
        "human": [
            "date",
            "body_load",
            "clarity",
            "stress",
            "sleep",
            "environment_feel",
            "human_phase",
            "human_energy",
        ],
        "household": [
            "date",
            "order",
            "noise",
            "clutter",
            "household_phase",
            "household_energy",
        ],
        "seasonal": [
            "date",
            "season",
            "inner_season",
            "light_cycle",
            "avg_temp",
            "seasonal_energy",
            "seasonal_phase",
        ],
        "harmony": [
            "date",
            "harmony_score",
            "hst_alignment",
            "drift_index",
            "readiness_level",
            "guidance",
        ],
    }

    for key, cols in expected.items():
        path = resolve_path(reg, "rhythms", key)
        if not path.exists():
            continue  # Creation is deferred to HST engine

        try:
            df = pd.read_csv(path, nrows=0)
        except Exception as e:
            errors.append(f"[CSV] Failed to read {path}: {e}")
            continue

        actual = list(df.columns)
        if actual != cols:
            errors.append(f"[CSV] Schema mismatch in {path}. Expected {cols}, got {actual}")

    return errors


def main() -> None:
    reg = load_registry()

    errors: list[str] = []
    errors += check_paths(reg)
    errors += check_files_exist(reg)
    errors += check_csv_headers(reg)

    print("══════════════════════════════════════")
    print("     SageOS — Consistency Checker")
    print("══════════════════════════════════════")

    if not errors:
        print("All checks passed. SageOS structure is consistent.")
    else:
        for e in errors:
            print(e)

    print("══════════════════════════════════════")


if __name__ == "__main__":
    main()
