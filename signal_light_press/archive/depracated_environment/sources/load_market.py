# rhythm_os/core/sources/load_market.py

from __future__ import annotations

from pathlib import Path
import pandas as pd

from .market_shield import run_market_shield

# --------------------------------------------------------------
# Paths
# --------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]    # -> SignalLogic
DATA_ROOT = ROOT / "data"
MARKET_DIR = DATA_ROOT / "market"
OUTPUT_PATH = MARKET_DIR / "market_rhythm.csv"


def load_market(days: int = 365) -> pd.DataFrame:
    """
    Load / update market_rhythm.csv using Market Ingestion Shield (MIS v1).

    Behavior (unchanged):
        • Calls run_market_shield(days, write_files=True)
        • Ensures SP500Close / VIXClose are present and NaN-free (shield responsibility)
        • Returns the cleaned DataFrame

    Rules:
        • NO print()
        • Raise on failure
    """
    df = run_market_shield(days=days, write_files=True)
    return df


if __name__ == "__main__":
    # Core stays silent even when invoked as a module.
    load_market()
