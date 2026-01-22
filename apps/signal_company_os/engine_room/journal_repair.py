# rhythm_os/core/journal_repair.py
"""
Rhythm OS — Journal Repair Tool v1.1

Fixes signal_journal.csv by syncing from merged_signal.csv:
  - Fills missing dates (ex: 2025-12-12)
  - Backfills Amplitude (and any other missing journal fields that exist in merged)
  - Never overwrites non-NA journal values (safe fill only)

Run once:
  python -m rhythm_os.core.journal_repair
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]  # -> SignalLogic/
DATA = ROOT / "data"

MERGED_PATH = DATA / "merged" / "merged_signal.csv"
JOURNAL_DIR = DATA / "journal"
JOURNAL_PATH = JOURNAL_DIR / "signal_journal.csv"


def _to_dt(s) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def main() -> None:
    print("[JOURNAL] Repair starting...")

    if not MERGED_PATH.exists():
        print(f"[JOURNAL] ❌ merged_signal.csv not found: {MERGED_PATH}")
        return

    m = pd.read_csv(MERGED_PATH)
    if m.empty or "Date" not in m.columns:
        print("[JOURNAL] ❌ merged_signal.csv empty or missing Date.")
        return

    m["Date"] = _to_dt(m["Date"])
    m = m.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    if JOURNAL_PATH.exists():
        j = pd.read_csv(JOURNAL_PATH)
        if "Date" not in j.columns:
            print("[JOURNAL] ❌ signal_journal.csv missing Date column.")
            return
        j["Date"] = _to_dt(j["Date"])
        j = j.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    else:
        # If no journal yet, create one using merged columns
        j = pd.DataFrame(columns=m.columns)
        j["Date"] = pd.to_datetime(j["Date"], errors="coerce")

    # --- Ensure Date is ONLY a column before indexing ---
    # If Date duplicated (rare), keep the first
    if "Date" in j.columns:
        j = j.loc[:, ~j.columns.duplicated()]

    # Index by Date (temporary)
    j_idx = j.set_index("Date", drop=True)
    m_idx = m.set_index("Date", drop=True)

    # Ensure journal contains every date from merged
    missing_dates = m_idx.index.difference(j_idx.index)
    if len(missing_dates) > 0:
        # Create real rows from merged for those missing dates (not all-NA placeholders)
        add_rows = m_idx.loc[missing_dates].copy()
        # Ensure add_rows has all journal columns
        for c in j_idx.columns:
            if c not in add_rows.columns:
                add_rows[c] = pd.NA
        add_rows = add_rows[j_idx.columns]  # align exactly
        j_idx = pd.concat([j_idx, add_rows], axis=0)

    # Safe-fill: for columns that exist in both, fill journal NA from merged
    common_cols = [c for c in j_idx.columns if c in m_idx.columns]
    filled_cells = 0

    for col in common_cols:
        before = int(j_idx[col].isna().sum())
        j_idx[col] = j_idx[col].fillna(m_idx[col])
        after = int(j_idx[col].isna().sum())
        filled_cells += max(0, before - after)

    # Back to column form
    out = j_idx.reset_index()  # index name is Date, so this inserts Date exactly once
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    out.to_csv(JOURNAL_PATH, index=False)

    # Report
    print("[JOURNAL] ✅ Repair complete.")
    print(f"[JOURNAL] Path: {JOURNAL_PATH}")
    print(f"[JOURNAL] Rows: {len(out)}")
    print(f"[JOURNAL] Filled cells (safe-fill): {filled_cells}")

    # Quick amplitude sanity
    if "Amplitude" in out.columns:
        tail = out.tail(30)[["Date", "Amplitude"]]
        nan_tail = int(pd.to_numeric(tail["Amplitude"], errors="coerce").isna().sum())
        print(f"[JOURNAL] Amplitude NaNs in last 30 rows: {nan_tail}")

    # Quick missing date sanity (contiguity check)
    dates = out["Date"].dt.date
    print(f"[JOURNAL] Date range: {dates.min()} → {dates.max()}")


if __name__ == "__main__":
    main()
