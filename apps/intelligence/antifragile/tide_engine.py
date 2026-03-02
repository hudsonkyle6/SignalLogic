import sys
from pathlib import Path

import pandas as pd

# -----------------------------
# Paths & config
# -----------------------------
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
JOURNAL_PATH = DATA_DIR / "journal" / "signal_journal.csv"
HUMAN_DIR = DATA_DIR / "human"
HUMAN_LEDGER_PATH = HUMAN_DIR / "human_ledger.csv"
TIDE_PATH = HUMAN_DIR / "tide_index.csv"

# Season → baseline load weight (0–1)
SEASON_LOAD_MAP = {
    "Build": 0.8,
    "Fuel": 0.6,
    "Tend": 0.4,
    "Reflect": 0.2,
}


def ensure_human_dirs():
    HUMAN_DIR.mkdir(parents=True, exist_ok=True)


def compute_tide_index():
    """
    Compute Tide Engine metrics for all dates in signal_journal.
    Returns a DataFrame with:
        Date, Season, TempAvg, MoonIllum, VIXClose,
        TempAnomaly, TempComponent,
        MoonPressure, MarketPressure,
        SeasonalLoadIndex,
        EnvPressureIndex, EnergyWindow
    """
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"signal_journal.csv not found at {JOURNAL_PATH}. "
            "Run kernel + journal build first."
        )

    df = pd.read_csv(JOURNAL_PATH)

    # Basic clean-up
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    required = ["TempAvg", "MoonIllum", "VIXClose", "Season"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"signal_journal is missing required column: {col}")

    # Temperature anomaly relative to seasonal mean
    season_means = df.groupby("Season")["TempAvg"].transform("mean")
    temp_anom = df["TempAvg"] - season_means

    # TempComponent: magnitude of anomaly (capped, scaled 0–1)
    temp_component = (temp_anom.abs() / 15.0).clip(0.0, 1.0)

    # MoonPressure: stronger near extremes (new/full), weaker near half
    moon_component = (4.0 * (df["MoonIllum"] - 0.5).abs()).clip(0.0, 2.0) / 2.0

    # MarketPressure: based on VIX (rough heuristic)
    market_component = ((df["VIXClose"] - 10.0) / 30.0).clip(0.0, 1.0)

    # Seasonal load baseline
    seasonal_load = df["Season"].map(SEASON_LOAD_MAP).fillna(0.5)

    # Environmental pressure index: weighted blend (0–1)
    env_pressure = (
        0.4 * temp_component + 0.3 * moon_component + 0.3 * market_component
    ).clip(0.0, 1.0)

    # Energy Window classification
    energy_window = []
    for val in env_pressure:
        if val >= 0.66:
            energy_window.append("Conserve")
        elif val <= 0.33:
            energy_window.append("Expand")
        else:
            energy_window.append("Neutral")

    out = pd.DataFrame(
        {
            "Date": df["Date"],
            "Season": df["Season"],
            "TempAvg": df["TempAvg"],
            "MoonIllum": df["MoonIllum"],
            "VIXClose": df["VIXClose"],
            "TempAnomaly": temp_anom,
            "TempComponent": temp_component,
            "MoonPressure": moon_component,
            "MarketPressure": market_component,
            "SeasonalLoadIndex": seasonal_load,
            "EnvPressureIndex": env_pressure,
            "EnergyWindow": energy_window,
        }
    )

    return out


def merge_tide_into_ledger(tide_df: pd.DataFrame):
    """
    If human_ledger exists, merge Tide Engine metrics into it
    by Date for any matching days.
    """
    if not HUMAN_LEDGER_PATH.exists():
        return

    ledger = pd.read_csv(HUMAN_LEDGER_PATH)

    # Normalize date formats
    ledger["Date"] = pd.to_datetime(ledger["Date"], errors="coerce")
    tide_df = tide_df.copy()
    tide_df["Date"] = pd.to_datetime(tide_df["Date"], errors="coerce")

    # Select columns to merge
    tide_cols = [
        "Date",
        "TempAnomaly",
        "TempComponent",
        "MoonPressure",
        "MarketPressure",
        "SeasonalLoadIndex",
        "EnvPressureIndex",
        "EnergyWindow",
    ]

    merged = ledger.merge(
        tide_df[tide_cols],
        on="Date",
        how="left",
        suffixes=("", "_tide"),
    )

    # Write back with Date as string
    merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")
    merged.to_csv(HUMAN_LEDGER_PATH, index=False)
    print(f"🔁 human_ledger updated with Tide Engine fields → {HUMAN_LEDGER_PATH}")


def run_tide_engine():
    """
    CLI entry point: compute Tide Index for all journal dates,
    write tide_index.csv, and merge today's tide into human_ledger.
    """
    ensure_human_dirs()

    tide_df = compute_tide_index()
    tide_df.to_csv(TIDE_PATH, index=False)
    print(f"📘 Tide Index written → {TIDE_PATH}")
    print(f"   Rows: {len(tide_df)}")

    # Merge into human ledger if present
    merge_tide_into_ledger(tide_df)

    # Show today's tide snapshot
    latest = tide_df.sort_values("Date").iloc[-1]
    print("══════════════════════════════════════")
    print("     🌊 TIDE ENGINE — TODAY SNAPSHOT")
    print("══════════════════════════════════════")
    print(f" Date:              {latest['Date'].strftime('%Y-%m-%d')}")
    print(f" Season:            {latest['Season']}")
    print(f" TempAvg:           {latest['TempAvg']:.2f}")
    print(f" TempAnomaly:       {latest['TempAnomaly']:.2f}")
    print(f" MoonIllum:         {latest['MoonIllum']:.3f}")
    print(f" VIXClose:          {latest['VIXClose']:.2f}")
    print(f" EnvPressureIndex:  {latest['EnvPressureIndex']:.3f}")
    print(f" EnergyWindow:      {latest['EnergyWindow']}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    try:
        run_tide_engine()
    except Exception as e:
        print("❌ Error:", e)
        sys.exit(1)
