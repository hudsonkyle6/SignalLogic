# rhythm_os/core/backfill/market_backfill.py

from pathlib import Path
from datetime import datetime
import pandas as pd

from rhythm_os.core.sources.market_shield import run_market_shield

# Correct ROOT path
ROOT = Path(__file__).resolve().parents[3]     # -> SignalLogic
DATA_DIR = ROOT / "data"
MARKET_DIR = DATA_DIR / "market"
OUTPUT_PATH = MARKET_DIR / "market_rhythm.csv"


def backfill_market(days: int = 365):
    """
    Backfill/refresh market_rhythm.csv using Market Ingestion Shield v1.

    This wraps run_market_shield(days, write_files=True), so:
        • All yfinance ingestion passes through the shield
        • Fallback tiers are respected
        • market_shield.csv (diagnostic) and market_rhythm.csv are both written
    """
    print("💹 [market_backfill] Updating market_rhythm.csv with Market Ingestion Shield v1...")

    df = run_market_shield(days=days, write_files=True)

    print(f"   → Saved: {OUTPUT_PATH}")
    if not df.empty:
        print(f"   → Last date in file: {df['Date'].iloc[-1]}")
    else:
        print("   → WARNING: market_rhythm.csv is empty after shield run.")


if __name__ == "__main__":
    backfill_market()
