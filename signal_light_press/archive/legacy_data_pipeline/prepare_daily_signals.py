# rhythm_os/core/prepare_daily_signals.py
"""
ARCHIVED — Jan 2026

This module orchestrated the full pre-sovereign
Rhythm OS daily signal preparation pipeline.

Retired when Core was sealed as an append-only
observational substrate and all pipeline logic
was removed from Core jurisdiction.
"""

"""
Prepare daily signals for Rhythm OS (Silent).

Canonical responsibilities:
• Run signal preparation steps (NAT → MARKET → MERGE → AMP → RES → COUPLING)
• Attach Memory + Ghost (full v1.0)
• Write enriched merged_signal.csv

Rules:
• NO print()
• NO emoji
• NO journal writes
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pandas as pd

from rhythm_os.core.memory.afterglow import compute_memory_fields
from rhythm_os.core.memory.ghost import inject_ghost_layer, compute_ghost_metrics


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MERGED_PATH = DATA / "merged" / "merged_signal.csv"


def run_prepare_pipeline() -> None:
    # 1) NATURAL
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.sources.load_natural"],
        check=True,
        cwd=str(ROOT),
    )

    # 2) MARKET
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.sources.load_market"],
        check=True,
        cwd=str(ROOT),
    )

    # 3) MERGE
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.resonance.merge_signals"],
        check=True,
        cwd=str(ROOT),
    )

    # 4) AMPLITUDE
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.resonance.amplitude"],
        check=True,
        cwd=str(ROOT),
    )

    # 5) RESONANCE SCORE
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.resonance.resonance_score"],
        check=True,
        cwd=str(ROOT),
    )

    # 6) COUPLING
    subprocess.run(
        [sys.executable, "-m", "rhythm_os.core.coupling.coupling"],
        check=True,
        cwd=str(ROOT),
    )

    # 7) MEMORY + GHOST
    if not MERGED_PATH.exists():
        raise FileNotFoundError("merged_signal.csv missing — cannot attach Memory/Ghost")

    df = pd.read_csv(MERGED_PATH)

    df = compute_memory_fields(df)
    df = inject_ghost_layer(df)
    df = compute_ghost_metrics(df)

    df.to_csv(MERGED_PATH, index=False)


if __name__ == "__main__":
    run_prepare_pipeline()
