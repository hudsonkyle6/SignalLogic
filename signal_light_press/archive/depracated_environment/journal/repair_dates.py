import pandas as pd
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]    # → SignalLogic/
JOURNAL = os.path.join(ROOT, "data", "journal", "signal_journal.csv")

def try_parse(date_str):
    """Try multiple formats, return normalized DD-MM-YY or None."""
    if pd.isna(date_str) or str(date_str).strip() == "":
        return None

    s = str(date_str).strip()

    # Supported formats
    fmts = [
        "%d-%m-%y",   # 23-11-24
        "%d-%m-%Y",   # 23-11-2024
        "%Y-%m-%d",   # 2024-11-23
        "%m-%d-%Y",   # 11-23-2024 (rare but some logs have this)
        "%m-%d-%y",   # 11-23-24
    ]

    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d-%m-%y")
        except:
            continue

    return None


def repair_dates():
    print("📘 Repairing journal dates...")
    print("   →", JOURNAL)

    df = pd.read_csv(JOURNAL)

    if "Date" not in df.columns:
        raise RuntimeError("signal_journal.csv has no 'Date' column!")

    # Normalize dates
    normalized = df["Date"].apply(try_parse)

    df["Date"] = normalized

    # Drop rows where date could not be repaired
    before = len(df)
    df = df.dropna(subset=["Date"])
    after = len(df)

    print(f"   → Normalized dates: {before} → {after}")
    print("   → Writing cleaned journal...")

    df.to_csv(JOURNAL, index=False)

    print("✅ repair_dates complete.")
    print("   All dates are now DD-MM-YY format.")


if __name__ == "__main__":
    repair_dates()
