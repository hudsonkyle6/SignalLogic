# -------------------------------------------------------------
#  ENVIRONMENT FETCHER — V4.1 (Local-Day Safe)
#  • Fetch hourly weather from Open-Meteo
#  • Aggregate daily averages
#  • NEVER write future days (fixes "Last Day" printing tomorrow)
#  • Merge into existing environment_rhythm.csv (no history loss)
# -------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests

# ---------------------------------------------------------
# TRUE SYSTEM ROOT (SignalLogic/)
# file is: SignalLogic/rhythm_os/core/environment/environment.py
# parents[3] => SignalLogic/
# ---------------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
ENV_DIR = DATA / "environment"
ENV_PATH = ENV_DIR / "environment_rhythm.csv"

# New Hampshire (approx)
LAT = 43.0
LON = -71.5

LOCAL_TZ = "America/New_York"


def fetch_environment(days_back: int = 7) -> None:
    print("[ENV] Updating environment_rhythm...")

    tz = ZoneInfo(LOCAL_TZ)
    today_local = datetime.now(tz).date()

    # Fetch a small buffer window, but we will filter out future days on write.
    start = today_local - timedelta(days=days_back)
    end = today_local + timedelta(days=1)  # safe buffer for API; filtered before save

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={LAT}&longitude={LON}"
        "&hourly=temperature_2m,pressure_msl,windspeed_10m"
        f"&start_date={start}&end_date={end}"
        f"&timezone={LOCAL_TZ}"
    )

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ENV] ❌ Fetch failed: {e}")
        return

    if "hourly" not in data or "time" not in data["hourly"]:
        print("[ENV] ❌ Open-Meteo returned no hourly data.")
        return

    hourly = data["hourly"]
    df = pd.DataFrame(hourly)

    # Rename to canonical cols
    df = df.rename(
        columns={
            "temperature_2m": "temp",
            "pressure_msl": "pressure",
            "windspeed_10m": "wind",
        }
    )

    # Parse timestamps in local timezone and derive local Date
    t = pd.to_datetime(df["time"], errors="coerce")
    df["Date"] = t.dt.date

    # Numeric safety
    for c in ["temp", "pressure", "wind"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Daily aggregation
    daily = (
        df.groupby("Date", as_index=False)[["temp", "pressure", "wind"]]
        .mean()
        .dropna(subset=["Date"])
    )

    # ✅ CRITICAL FIX: never allow future days into the file
    daily = daily[daily["Date"] <= today_local].copy()

    # Write/merge
    ENV_DIR.mkdir(parents=True, exist_ok=True)

    if ENV_PATH.exists():
        try:
            existing = pd.read_csv(ENV_PATH)
            if "Date" in existing.columns:
                existing["Date"] = pd.to_datetime(existing["Date"], errors="coerce").dt.date
            merged = pd.concat([existing, daily], ignore_index=True)
        except Exception:
            merged = daily.copy()
    else:
        merged = daily.copy()

    # Deduplicate by Date, keep newest
    merged = (
        merged.dropna(subset=["Date"])
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )

    merged.to_csv(ENV_PATH, index=False)
    print(f"[ENV] Saved → {ENV_PATH}")
    print(f"[ENV] Last day written: {merged['Date'].iloc[-1]}")


if __name__ == "__main__":
    fetch_environment()


