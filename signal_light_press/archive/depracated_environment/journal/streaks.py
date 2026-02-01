# rhythm_os/core/journal/streaks.py
"""
Rebuild StreakLength column for signal_journal.csv
after repairs or merges. This recreates the exact
kernel streak logic but in a vectorized, safe way.
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOURNAL = ROOT / "data" / "journal" / "signal_journal.csv"


def rebuild_streaks():
    print("📘 Rebuilding StreakLength in signal_journal.csv")
    print(f"   → Loading: {JOURNAL}")

    df = pd.read_csv(JOURNAL)

    # Ensure columns exist
    req_cols = ["Date", "SignalState", "PrevState", "ChangeType"]
    for col in req_cols:
        if col not in df.columns:
            raise RuntimeError(f"Missing column in journal: {col}")

    # Normalize dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date").reset_index(drop=True)

    streaks = []
    current = 0
    last_state = None

    for idx, row in df.iterrows():
        state = row["SignalState"]
        prev = row["PrevState"]
        change = row["ChangeType"]

        # If this is the first row → streak = 1
        if idx == 0:
            current = 1
            streaks.append(current)
            last_state = state
            continue

        # Kernel rule 1 — If ChangeType == "Flip" → reset
        if isinstance(change, str) and change.lower() == "flip":
            current = 1

        # Kernel rule 2 — If state == last_state → increment
        elif state == last_state:
            current += 1

        # Kernel rule 3 — Everything else → reset
        else:
            current = 1

        streaks.append(current)
        last_state = state

    df["StreakLength"] = streaks

    print(f"   → Streaks rebuilt for {len(df)} rows")
    print(f"   → Saving: {JOURNAL}")

    df.to_csv(JOURNAL, index=False)
    print("✅ Streak rebuild complete.")


if __name__ == "__main__":
    rebuild_streaks()
