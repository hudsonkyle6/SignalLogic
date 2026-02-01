# rhythm_os/core/backfill.py

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ..loader import load_smoothed_merged_signal
from ..state_machine import StateMachine, TodaySnapshot


ROOT = Path(__file__).resolve().parents[3]  # -> SignalLogic
DATA_DIR = ROOT / "data"
SIGNAL_JOURNAL = ROOT / "data" / "journal"
JOURNAL_PATH = SIGNAL_JOURNAL / "signal_journal.csv"


def run_backfill() -> None:
    print("📒 Rhythm OS Backfill — Rebuild Journal")

    # 1) Backup existing journal if present
    if JOURNAL_PATH.exists():
        backup = JOURNAL_PATH.with_suffix(".backup.csv")
        JOURNAL_PATH.replace(backup)
        print(f"🗂️  Existing journal backed up to: {backup}")

    # 2) Load smoothed merged_signal via Loader V2
    df = load_smoothed_merged_signal()
    if df.empty:
        raise RuntimeError("Smoothed merged_signal DataFrame is empty — nothing to backfill.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Backfill up through *yesterday*.
    # Today's row will be handled by the live kernel.
    today = datetime.now().date()
    hist_df = df[df["Date"].dt.date < today].copy()

    if hist_df.empty:
        print("⚠️  No historical rows before today to backfill.")
        return

    sm = StateMachine(journal_path=JOURNAL_PATH)

    total = len(hist_df)
    print(f"🔁 Replaying {total} day(s) into StateMachine...")

    for idx, row in hist_df.iterrows():
        snap = TodaySnapshot(
            date=row["Date"],
            season=str(row.get("Season", "Unknown")),
            state=row.get("SignalState", "Unknown"),
            resonance=float(row.get("ResonanceValue", 0.0) or 0.0),

            sp_close=float(row["SP500Close"]) if "SP500Close" in row and pd.notna(row["SP500Close"]) else None,
            vix_close=float(row["VIXClose"]) if "VIXClose" in row and pd.notna(row["VIXClose"]) else None,
            temp_avg=float(row["TempAvg"]) if "TempAvg" in row and pd.notna(row["TempAvg"]) else None,
            moon_illum=float(row["MoonIllum"]) if "MoonIllum" in row and pd.notna(row["MoonIllum"]) else None,

            # For now we don't backfill coupling history
            coupling_col=None,
            coupling_lag=None,
            coupling_pearson=None,
        )

        mem = sm.evaluate(snap)

        # progress log
        if (idx + 1) % 25 == 0 or (idx + 1) == total:
            print(
                f"   [{idx+1}/{total}] {snap.date.date()} "
                f"state={snap.state} phase={mem['Phase']} streak={mem['StreakLength']}"
            )

    print("\n✅ Backfill complete.")
    print(f"   Final journal written to: {JOURNAL_PATH}")


if __name__ == "__main__":
    run_backfill()
