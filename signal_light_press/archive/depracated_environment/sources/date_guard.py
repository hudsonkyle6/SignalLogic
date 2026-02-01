import pandas as pd
from pathlib import Path

def scrub_journal_dates(journal_path):
    journal_path = Path(journal_path)

    # --------------------------------------------------
    # GUARD: journal may not exist yet (first run / reset)
    # --------------------------------------------------
    if not journal_path.exists():
        print("[DATE_GUARD] Journal missing — skipping date scrub.")
        return

    df = pd.read_csv(journal_path)

    if df.empty or "Date" not in df.columns:
        print("[DATE_GUARD] Journal empty or no Date column — skipping.")
        return

    # Ensure Date is datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Drop invalid rows
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    df.to_csv(journal_path, index=False)
    print("[DATE_GUARD] Journal dates scrubbed.")
