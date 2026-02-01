"""
Rhythm OS — Coupling Backfill V2.1 (HST aligned, journal-centric)

Purpose:
    Recompute coupling metrics for every row in signal_journal.csv
    using merged_signal.csv as the canonical natural/market driver
    source.

Inputs:
    • data/journal/signal_journal.csv
        - Date
        - ResonanceValue
        - (optionally) Amplitude

    • data/merged/merged_signal.csv
        - Date
        - TempAvg
        - MoonIllum
        - SP500Close
        - VIXClose
        - Amplitude

Outputs (written back into signal_journal.csv):
    • CouplingCol
    • CouplingLag
    • CouplingPearson
    • AmpCouplingCol
    • AmpCouplingLag
    • AmpCouplingPearson
"""

from __future__ import annotations

from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]  # → SignalLogic/
DATA_DIR = ROOT / "data"

JOURNAL_PATH = DATA_DIR / "journal" / "signal_journal.csv"
MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"

BACKUP_SUFFIX = ".coupling_backup_{stamp}.csv"

# Natural / market drivers we consider for coupling
NAT_COLS = ["MoonIllum", "TempAvg", "SP500Close", "VIXClose"]

# Coupling windows & lags
WINDOW_DAYS = 30        # lookback window
MAX_LAG = 7             # days; we only use non-negative lags (0..7)


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def _parse_date_series(series: pd.Series, dayfirst: bool = True) -> pd.Series:
    """
    Parse a Date column robustly.

    We allow DD-MM-YY style journal dates (dayfirst=True)
    and ISO dates from merged (dayfirst=False).
    """
    return pd.to_datetime(series, errors="coerce", dayfirst=dayfirst)


def _pearson_safe(x: pd.Series, y: pd.Series) -> float:
    """
    Safe Pearson correlation: returns np.nan if insufficient points.
    """
    mask = x.notna() & y.notna()
    if mask.sum() < 5:
        return np.nan
    xv = x[mask].to_numpy(dtype=float)
    yv = y[mask].to_numpy(dtype=float)
    if xv.size < 2:
        return np.nan
    r = np.corrcoef(xv, yv)[0, 1]
    if np.isnan(r):
        return np.nan
    return float(r)


def _series_window(
    s: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    """
    Slice a series in [start, end], reindex to full daily range.
    """
    idx = pd.date_range(start, end, freq="D")
    # Reindex with daily grid so lags line up.
    return s.reindex(idx)


def _best_coupling(
    target_series: pd.Series,
    drivers: dict[str, pd.Series],
    center_date: pd.Timestamp,
    window_days: int = WINDOW_DAYS,
    max_lag: int = MAX_LAG,
) -> tuple[str | float, float | float, float | float]:
    """
    Compute best (absolute) Pearson coupling between target_series and
    provided drivers over a rolling window ending at center_date.

    Returns:
        (best_col_name, best_lag, best_r)
        If no valid correlation, returns (np.nan, np.nan, np.nan).
    """
    start = center_date - timedelta(days=window_days)
    end = center_date

    # Build a daily grid window for the *target*.
    target_win = _series_window(target_series, start, end)

    best_col = np.nan
    best_lag = np.nan
    best_r = np.nan
    best_abs = 0.0

    for col_name, driver_series in drivers.items():
        if driver_series is None:
            continue

        driver_win = _series_window(driver_series, start, end)

        for lag in range(0, max_lag + 1):
            shifted = driver_win.shift(lag)
            r = _pearson_safe(target_win, shifted)
            if np.isnan(r):
                continue

            if abs(r) > best_abs:
                best_abs = abs(r)
                best_col = col_name
                best_lag = float(lag)
                best_r = float(r)

    return best_col, best_lag, best_r


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> None:
    print("📡 Rhythm OS — Coupling Backfill V2.1 (HST aligned, journal-centric)")
    print(f"Root:    {ROOT}")
    print(f"Journal: {JOURNAL_PATH}")
    print(f"Merged:  {MERGED_PATH}")

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(f"signal_journal.csv not found at {JOURNAL_PATH}")

    if not MERGED_PATH.exists():
        raise FileNotFoundError(f"merged_signal.csv not found at {MERGED_PATH}")

    # ---------------------------------------------------------------
    # Load journal & merged
    # ---------------------------------------------------------------
    journal = pd.read_csv(JOURNAL_PATH)
    merged = pd.read_csv(MERGED_PATH)

    # Parse dates
    journal["Date"] = _parse_date_series(journal["Date"], dayfirst=True)
    merged["Date"] = _parse_date_series(merged["Date"], dayfirst=False)

    journal = journal.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    merged = merged.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Index helpers
    journal = journal.set_index("Date")
    merged = merged.set_index("Date")

    # Ensure required columns exist
    if "ResonanceValue" not in journal.columns:
        raise ValueError("signal_journal.csv missing 'ResonanceValue' column.")

    # Amplitude for amp-coupling: prefer merged, fall back to journal if present there.
    if "Amplitude" in merged.columns:
        amp_series = merged["Amplitude"]
    elif "Amplitude" in journal.columns:
        amp_series = journal["Amplitude"]
        print("   ⚠️ Using Amplitude from journal (merged missing it).")
    else:
        amp_series = None
        print("   ⚠️ No Amplitude column found — AmpCoupling* will remain NaN.")

    # Target series (journal-based)
    res_series = journal["ResonanceValue"]

    # Driver series (merged)
    drivers_res = {}
    for col in NAT_COLS:
        if col in merged.columns:
            drivers_res[col] = merged[col]
        else:
            drivers_res[col] = None

    drivers_amp = drivers_res.copy()

    # ---------------------------------------------------------------
    # Backup before modifications
    # ---------------------------------------------------------------
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    backup_path = JOURNAL_PATH.with_name(
        JOURNAL_PATH.stem + BACKUP_SUFFIX.format(stamp=stamp)
    )
    journal.reset_index().to_csv(backup_path, index=False)
    print(f"💾 Backup saved → {backup_path.name}")
    print("\n🔁 Recomputing coupling for all journal dates…")

    # ---------------------------------------------------------------
    # Iterate rows and compute couplings
    # ---------------------------------------------------------------
    # Make sure we iterate in chronological order
    dates = journal.index.sort_values().unique()
    total = len(dates)

    # Prepare result arrays
    coupling_col = []
    coupling_lag = []
    coupling_r = []
    amp_coupling_col = []
    amp_coupling_lag = []
    amp_coupling_r = []

    for i, d in enumerate(dates, start=1):
        if i == 1 or i % 25 == 0:
            print(f"   processed {i}/{total} rows… ({d.date()})")

        # If resonance is NaN for this date, just push NaNs and continue
        if pd.isna(res_series.get(d, np.nan)):
            coupling_col.append(np.nan)
            coupling_lag.append(np.nan)
            coupling_r.append(np.nan)
            amp_coupling_col.append(np.nan)
            amp_coupling_lag.append(np.nan)
            amp_coupling_r.append(np.nan)
            continue

        # --- Resonance coupling ---
        col_res, lag_res, r_res = _best_coupling(
            target_series=res_series,
            drivers=drivers_res,
            center_date=d,
            window_days=WINDOW_DAYS,
            max_lag=MAX_LAG,
        )

        coupling_col.append(col_res)
        coupling_lag.append(lag_res)
        coupling_r.append(r_res)

        # --- Amplitude coupling ---
        if amp_series is not None:
            col_amp, lag_amp, r_amp = _best_coupling(
                target_series=amp_series,
                drivers=drivers_amp,
                center_date=d,
                window_days=WINDOW_DAYS,
                max_lag=MAX_LAG,
            )
        else:
            col_amp = np.nan
            lag_amp = np.nan
            r_amp = np.nan

        amp_coupling_col.append(col_amp)
        amp_coupling_lag.append(lag_amp)
        amp_coupling_r.append(r_amp)

    # ---------------------------------------------------------------
    # Attach results back to journal & save
    # ---------------------------------------------------------------
    journal["CouplingCol"] = coupling_col
    journal["CouplingLag"] = coupling_lag
    journal["CouplingPearson"] = coupling_r

    journal["AmpCouplingCol"] = amp_coupling_col
    journal["AmpCouplingLag"] = amp_coupling_lag
    journal["AmpCouplingPearson"] = amp_coupling_r

    # Write back (restore Date as column)
    out_df = journal.reset_index()
    out_df.to_csv(JOURNAL_PATH, index=False)

    print("\n✅ Coupling backfill complete.")
    print(f"   → Updated file: {JOURNAL_PATH}")
    print(f"   → Rows: {len(out_df)}")


if __name__ == "__main__":
    main()
