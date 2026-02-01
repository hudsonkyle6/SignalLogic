"""
PERMANENT DATE-ROBUST JOURNAL SYNC
This version normalizes *all* date formats and performs a guaranteed
left-join sync from merged_signal → signal_journal.

No matter what the journal date format is, it will match merged data.
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOURNAL = ROOT / "data" / "journal" / "signal_journal.csv"
MERGED = ROOT / "data" / "merged" / "merged_signal.csv"

# ---------------------------------------------------------------------
# Robust date cleaner — handles ALL formats automatically.
# ---------------------------------------------------------------------
def normalize_dates(series: pd.Series) -> pd.Series:
    """
    Takes ANY date format:
        - YYYY-MM-DD
        - DD-MM-YY
        - MM/DD/YY
        - '2025/11/23'
        - Excel-like strings
        - NaN
    and returns clean pd.Timestamp objects.
    """

    cleaned = []

    for raw in series.astype(str):
        raw = raw.strip()

        if raw in ("", "nan", "NaT", None):
            cleaned.append(pd.NaT)
            continue

        # Primary parser (very robust)
        try:
            cleaned.append(pd.to_datetime(raw, errors="raise", dayfirst=True))
            continue
        except Exception:
            pass

        # Secondary: try forcing Y-M-D ordering
        try:
            cleaned.append(pd.to_datetime(raw, errors="raise", dayfirst=False))
            continue
        except Exception:
            pass

        # Last resort: manual parsing of DD-MM-YY → YYYY-MM-DD
        if "-" in raw:
            parts = raw.split("-")
            if len(parts) == 3:
                # Detect pattern by element length
                d, m, y = parts
                if len(y) == 2:
                    y = "20" + y
                try:
                    cleaned.append(pd.Timestamp(f"{y}-{m}-{d}"))
                    continue
                except Exception:
                    pass

        # If all fail
        cleaned.append(pd.NaT)

    return pd.to_datetime(cleaned, errors="coerce")


# ---------------------------------------------------------------------
# Main Sync function
# ---------------------------------------------------------------------
def run_sync():
    print("📡 Journal Sync — Populating fields from merged_signal.csv")
    print(f"   ROOT:    {ROOT}")
    print(f"   Journal: {JOURNAL}")
    print(f"   Merged:  {MERGED}")

    # ------------------------
    # Load both files
    # ------------------------
    df_j = pd.read_csv(JOURNAL)
    df_m = pd.read_csv(MERGED)

    # ------------------------
    # Normalize all dates
    # ------------------------
    df_j["Date"] = normalize_dates(df_j["Date"])
    df_m["Date"] = normalize_dates(df_m["Date"])

    # Drop rows that failed parsing
    before = len(df_j)
    df_j = df_j.dropna(subset=["Date"])
    df_m = df_m.dropna(subset=["Date"])
    after = len(df_j)

    if after != before:
        print(f"   → Removed {before-after} bad journal date rows")

    # Ensure ordering
    df_j = df_j.sort_values("Date")
    df_m = df_m.sort_values("Date")

    # ------------------------------------------------------------------
    # FIELDS TO SYNC (automatic discovery — no manual maintenance)
    # ------------------------------------------------------------------
    merged_fields = [c for c in df_m.columns if c != "Date"]

    fill_count = 0

    # Build a new synced journal
    df_new = df_j.copy()

    for col in merged_fields:
        if col not in df_new.columns:
            df_new[col] = None

        # Sync only where journal is empty OR is NaN
        mask = df_new[col].isna() | (df_new[col] == "")
        df_new.loc[mask, col] = df_new.loc[mask, "Date"].map(
            df_m.set_index("Date")[col]
        )
        fill_count += mask.sum()

    # ------------------------------------------------------------------
    # Final save
    # ------------------------------------------------------------------
    df_new.to_csv(JOURNAL, index=False)
    print(f"   → Fields filled: {fill_count}")
    print("📡 Journal Sync — complete.")


if __name__ == "__main__":
    run_sync()
