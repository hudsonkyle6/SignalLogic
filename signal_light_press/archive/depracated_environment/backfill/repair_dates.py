# rhythm_os/core/backfill/repair_dates.py
"""
Repair ALL dates in signal_journal.csv
Preserve DD-MM-YY output format but ensure correct parsing.

Fixes:
  • Date drift (future dates accidentally created)
  • Mixed-format interpretation
  • Incorrect auto-parsed dates
  • Out-of-order entries

Final format: DD-MM-YY
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
JOURNAL_FILE = DATA / "journal" / "signal_journal.csv"


def parse_date_strict(d: str):
    """
    Force-parse DD-MM-YY as day-first.
    If parsing fails, return NaT.
    """
    try:
        return pd.to_datetime(d, dayfirst=True, errors="coerce")
    except:
        return pd.NaT


def main():
    print("📅 Rhythm OS — Journal Date Repair")
    print("Journal:", JOURNAL_FILE)

    if not JOURNAL_FILE.exists():
        print("❌ No journal file found.")
        return

    # ------------------------------------------------------------
    # Load journal
    # ------------------------------------------------------------
    df = pd.read_csv(JOURNAL_FILE, dtype=str)   # read all as strings so dates aren't corrupted

    if "Date" not in df.columns:
        print("❌ Journal missing Date column.")
        return

    # ------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = JOURNAL_FILE.with_name(f"signal_journal.date_backup_{ts}.csv")
    df.to_csv(backup, index=False)
    print(f"💾 Backup saved → {backup.name}")

    # ------------------------------------------------------------
    # Parse using strict DD-MM-YY
    # ------------------------------------------------------------
    print("🔁 Parsing dates with strict DD-MM-YY rule...")
    df["ParsedDate"] = df["Date"].apply(parse_date_strict)

    # Remove rows with unparseable dates
    df = df.dropna(subset=["ParsedDate"]).copy()

    # Remove accidental future dates (after today)
    today = pd.Timestamp.today().normalize()
    df = df[df["ParsedDate"] <= today].copy()

    # Sort chronologically
    df = df.sort_values("ParsedDate").reset_index(drop=True)

    # Output final date column back into DD-MM-YY format
    df["Date"] = df["ParsedDate"].dt.strftime("%d-%m-%y")

    # Remove helper column
    df = df.drop(columns=["ParsedDate"])

    # Save clean journal
    df.to_csv(JOURNAL_FILE, index=False)

    print("\n✅ Date repair complete!")
    print(f"📄 Cleaned journal saved → {JOURNAL_FILE.name}")
    print("Your timeline is now consistent, past-only, and sorted.\n")


if __name__ == "__main__":
    main()
