# rhythm_os/core/backfill/natural_backfill.py

from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import math

ROOT = Path(__file__).resolve().parents[3]  # -> SignalLogic/
DATA_DIR = ROOT / "data"
NAT_DIR = DATA_DIR / "natural"
NAT_PATH = NAT_DIR / "natural_rhythm.csv"


# -----------------------------------------------------------
# Moon illumination + moon age (true astronomical formula)
# -----------------------------------------------------------
def moon_illumination(date: datetime) -> float:
    """Return moon illumination 0.0–1.0 using simple synodic cycle."""
    # Days since known new moon: Jan 6, 2000
    known_new_moon = datetime(2000, 1, 6, 18, 14)
    days = (date - known_new_moon).total_seconds() / 86400.0

    synodic_month = 29.53058867
    phase = (days % synodic_month) / synodic_month  # 0–1

    # Illumination formula
    illum = 0.5 * (1 - math.cos(2 * math.pi * phase))
    return float(round(illum, 5))


def moon_age(date: datetime) -> float:
    """Return moon age in days."""
    known_new_moon = datetime(2000, 1, 6, 18, 14)
    days = (date - known_new_moon).total_seconds() / 86400.0
    return float(days % 29.53058867)


# -----------------------------------------------------------
# Synthetic temperature — smooth seasonal curve
# -----------------------------------------------------------
def seasonal_temp(date: datetime) -> float:
    """Generate realistic NH seasonal temperature curve."""
    day_of_year = date.timetuple().tm_yday
    # amplitude ~ 15°C swing
    # baseline ~ 8°C
    # shifted for NH climate
    temp = 8 + 15 * math.sin((2 * math.pi * (day_of_year - 170)) / 365)
    return float(round(temp, 2))


# -----------------------------------------------------------
# Map date → Season (Signal OS Seasons)
# -----------------------------------------------------------
def determine_season(date: datetime) -> str:
    month = date.month
    if month in (3, 4, 5):
        return "Build"
    if month in (6, 7, 8):
        return "Fuel"
    if month in (9, 10, 11):
        return "Tend"
    return "Reflect"


# -----------------------------------------------------------
# Main Backfill
# -----------------------------------------------------------
def backfill_natural(days: int = 365):
    print("🌿 [natural_backfill] Rebuilding natural_rhythm.csv (clean)…")

    NAT_DIR.mkdir(parents=True, exist_ok=True)

    end = datetime.today()
    start = end - timedelta(days=days)
    dates = pd.date_range(start, end, freq="D")

    rows = []
    for dt in dates:
        rows.append({
            "Date": dt,
            "TempAvg": seasonal_temp(dt),
            "MoonIllum": moon_illumination(dt),
            "MoonAge": moon_age(dt),
            "Season": determine_season(dt),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("Date")

    df.to_csv(NAT_PATH, index=False)
    print(f"   → Natural rhythm rebuilt: {NAT_PATH}")
    print(f"   → Rows: {len(df)}")


def main():
    return backfill_natural()


if __name__ == "__main__":
    main()

