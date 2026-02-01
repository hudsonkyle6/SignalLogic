# rhythm_os/core/sources/load_natural.py
"""
Natural Rhythm Updater — 10,000-Year Proof (V1.2 FIXED) — Silent

Fix preserved:
    • Convert date -> datetime for moon functions (avoids TypeError)

Rules:
    • NO print()
    • NO human-facing output
    • Raise on failure
"""

from __future__ import annotations

from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd

from rhythm_os.core.backfill.natural_backfill import (
    moon_illumination,
    moon_age,
    seasonal_temp,
    determine_season,
)

ROOT = Path(__file__).resolve().parents[3]  # → SignalLogic/
DATA_DIR = ROOT / "data"
NATURAL_DIR = DATA_DIR / "natural"
NATURAL_PATH = NATURAL_DIR / "natural_rhythm.csv"


def to_datetime(d: date) -> datetime:
    """Convert a date to a datetime so moon functions never break."""
    return datetime(d.year, d.month, d.day)


def update_natural_rhythm() -> pd.DataFrame:
    NATURAL_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()

    # -------------------------
    # Load or create file
    # -------------------------
    if NATURAL_PATH.exists():
        df = pd.read_csv(NATURAL_PATH)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
            df = df.dropna(subset=["Date"])
            last_date = df["Date"].max() if not df.empty else (today - timedelta(days=365))
        else:
            df = pd.DataFrame(columns=["Date", "TempAvg", "MoonIllum", "MoonAge", "Season"])
            last_date = today - timedelta(days=365)
    else:
        df = pd.DataFrame(columns=["Date", "TempAvg", "MoonIllum", "MoonAge", "Season"])
        last_date = today - timedelta(days=365)

    # Already up to date?
    if last_date >= today:
        return df

    start = last_date + timedelta(days=1)

    rows = []
    for d in pd.date_range(start=start, end=today, freq="D"):
        dd: date = d.date()
        dt = to_datetime(dd)  # FIXED: convert to datetime for moon models

        temp = seasonal_temp(dd)
        illum = moon_illumination(dt)
        age = moon_age(dt)
        season = determine_season(dd)

        rows.append(
            {
                "Date": dd.isoformat(),
                "TempAvg": temp,
                "MoonIllum": illum,
                "MoonAge": age,
                "Season": season,
            }
        )

    new_df = pd.DataFrame(rows)
    df_out = pd.concat([df, new_df], ignore_index=True)
    df_out.to_csv(NATURAL_PATH, index=False)

    return df_out


if __name__ == "__main__":
    # Core stays silent even when invoked as a module.
    update_natural_rhythm()

