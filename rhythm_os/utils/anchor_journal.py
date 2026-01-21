"""
ONE-TIME JOURNAL ANCHOR
----------------------
Aligns signal_journal.csv Date to the latest merged_signal.csv Date.

• Touches DATE ONLY
• Preserves all other values
• Safe to run once
• Exits immediately after success
"""

from pathlib import Path
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

MERGED_PATH = DATA / "merged" / "merged_signal.csv"
JOURNAL_PATH = DATA / "journal" / "signal_journal.csv"


def main():
    if not MERGED_PATH.exists():
        print("❌ merged_signal.csv not found.")
        sys.exit(1)

    if not JOURNAL_PATH.exists():
        print("❌ signal_journal.csv not found.")
        sys.exit(1)

    merged = pd.read_csv(MERGED_PATH)
    journal = pd.read_csv(JOURNAL_PATH)

    if journal.shape[0] != 1:
        print("❌ Journal has more than one row — aborting.")
        sys.exit(1)

    merged_date = merged.iloc[-1]["Date"]
    journal_date = journal.iloc[0]["Date"]

    if merged_date == journal_date:
        print("ℹ️ Journal already aligned. No action taken.")
        return

    journal.loc[0, "Date"] = merged_date
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    journal.to_csv(JOURNAL_PATH, index=False)

    print("✅ Journal anchored successfully.")
    print(f"   Old Date: {journal_date}")
    print(f"   New Date: {merged_date}")
    print("⚠️ Do not run this script again.")


if __name__ == "__main__":
    main()
