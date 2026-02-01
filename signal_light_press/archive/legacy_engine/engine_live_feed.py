# engine_live_feed.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
import requests
from datetime import datetime, timedelta
import math

DATA_PATH = Path(__file__).parent.parent / "data" / "natural_rhythm.csv"

def _moon_phase(date: datetime) -> tuple[float, float]:
    """Return (illumination fraction 0-1, age in days)."""
    diff = date - datetime(2001, 1, 1)  # reference new moon
    days = diff.days + (diff.seconds / 86400)
    lunations = 0.20439731 + days * 0.03386319269
    pos = lunations % 1
    illum = 0.5 * (1 - math.cos(2 * math.pi * pos))
    age = pos * 29.53
    return illum, age

def fetch_weather(lat: float, lon: float, days_back: int = 7) -> pd.DataFrame:
    """Fetch daily mean temperature via open-meteo."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days_back)
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        "&daily=temperature_2m_mean&timezone=auto"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "daily" not in data:
        raise RuntimeError("Unexpected weather response format.")
    df = pd.DataFrame({
        "Date": pd.to_datetime(data["daily"]["time"]),
        "TempAvg": data["daily"]["temperature_2m_mean"],
    })
    return df

def build_or_update(lat: float, lon: float, days_back: int = 7) -> pd.DataFrame:
    """Fetch new data, add moon columns, and update local CSV."""
    df_wx = fetch_weather(lat, lon, days_back)
    df_wx["MoonIllum"], df_wx["MoonAge"] = zip(*df_wx["Date"].apply(_moon_phase))

    if DATA_PATH.exists():
        old = pd.read_csv(DATA_PATH, parse_dates=["Date"])
        merged = pd.concat([old, df_wx], ignore_index=True)
        merged = merged.drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    else:
        merged = df_wx.sort_values("Date").reset_index(drop=True)

    merged.to_csv(DATA_PATH, index=False)
    return merged
