# rhythm_os/antifragile/weekly_signatures.py
"""
Antifragile Engine — Weekly Signatures (Canonical)

Authority:
- This file is the ONLY writer of data/human/weekly_signatures.csv
- Enforces: one row per ISO year-week (idempotent rebuild)

Source:
- data/human/human_ledger.csv
- data/merged/merged_signal.csv (via ledger join fields)

Output:
- data/human/weekly_signatures.csv

Design Law:
- Assist Under Discipline
- Observability only (no authority, no escalation)
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from ...kernel.wave import Wave  # three dots for one level up
from ...kernel.codex import Codex
# -------------------------------------------------
# Observability window configuration (AUD-safe)
# -------------------------------------------------
WINDOW_DAYS = 7
MIN_PERIODS = 3

# -------------------------------------------------
# Paths
# -------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
HUMAN = DATA / "human"

LEDGER_PATH = HUMAN / "human_ledger.csv"
WEEKLY_PATH = HUMAN / "weekly_signatures.csv"

# -------------------------------------------------
# Canonical output schema (explicit, ordered)
# -------------------------------------------------
CANON_COLS = [
    "ISOYear",
    "ISOWeek",
    "WeekEnd",
    "DaysLogged",
    "Season",
    "InnerSeason",

    # Weekly means
    "AvgBodyLoad",
    "AvgClarity",
    "AvgResistance",
    "AvgStress",
    "AvgSleep",
    "AvgEnvFeel",
    "AvgResonance",
    "AvgAmplitude",

    # Observability windows (non-authoritative)
    "AvgBodyLoadWindow",
    "AvgClarityWindow",
    "AvgStressWindow",
    "AvgResonanceWindow",
    "AvgAmplitudeWindow",

    # Weekly descriptors
    "DecisionState_Mode",
    "HighPoint",
    "LowPoint",
    "ClarityTrend",
    "StressTrend",
]

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as e:
        print(f"⚠ Could not read {path}: {e}", file=sys.stderr)
        return pd.DataFrame()

def _to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _mode(series: pd.Series) -> str:
    if series is None or series.empty:
        return ""
    m = series.dropna().astype(str).mode()
    return m.iloc[0] if not m.empty else ""

def _week_end_date(dts: pd.Series) -> str:
    mx = pd.to_datetime(dts, errors="coerce").max()
    return mx.strftime("%Y-%m-%d") if pd.notna(mx) else ""

def _latest(series: pd.Series):
    s = series.dropna()
    return float(s.iloc[-1]) if not s.empty else np.nan

# -------------------------------------------------
# Main builder
# -------------------------------------------------
def build_weekly_signatures() -> None:
    HUMAN.mkdir(parents=True, exist_ok=True)

    ledger = _safe_read_csv(LEDGER_PATH)
    if ledger.empty:
        raise ValueError(f"{LEDGER_PATH} is missing or empty.")

    # Normalize Date
    ledger["Date"] = pd.to_datetime(ledger["Date"], errors="coerce")
    ledger = ledger.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # ISO week keys
    iso = ledger["Date"].dt.isocalendar()
    ledger["ISOYear"] = iso.year.astype(int)
    ledger["ISOWeek"] = iso.week.astype(int)

    # Seasonal fallback
    if "InnerSeason" not in ledger.columns:
        ledger["InnerSeason"] = ledger.get("Season", "")

    # Ensure numeric columns exist
    cols = {
        "BodyLoad": "AvgBodyLoad",
        "Clarity": "AvgClarity",
        "Resistance": "AvgResistance",
        "StressLevel": "AvgStress",
        "SleepQuality": "AvgSleep",
        "EnvFeel": "AvgEnvFeel",
        "ResonanceValue": "AvgResonance",
        "Amplitude": "AvgAmplitude",
    }
    for c in cols:
        if c not in ledger.columns:
            ledger[c] = np.nan

    # -------------------------------------------------
    # Daily rolling observability windows (AUD-safe)
    # -------------------------------------------------
    ledger["AvgBodyLoadWindow"] = (
        _to_float(ledger["BodyLoad"])
        .rolling(WINDOW_DAYS, min_periods=MIN_PERIODS)
        .mean()
    )

    ledger["AvgClarityWindow"] = (
        _to_float(ledger["Clarity"])
        .rolling(WINDOW_DAYS, min_periods=MIN_PERIODS)
        .mean()
    )

    ledger["AvgStressWindow"] = (
        _to_float(ledger["StressLevel"])
        .rolling(WINDOW_DAYS, min_periods=MIN_PERIODS)
        .mean()
    )

    ledger["AvgResonanceWindow"] = (
        _to_float(ledger["ResonanceValue"])
        .rolling(WINDOW_DAYS, min_periods=MIN_PERIODS)
        .mean()
    )

    ledger["AvgAmplitudeWindow"] = (
        _to_float(ledger["Amplitude"])
        .rolling(WINDOW_DAYS, min_periods=MIN_PERIODS)
        .mean()
    )

    # -------------------------------------------------
    # Weekly aggregation
    # -------------------------------------------------
    out_rows = []
    grouped = ledger.groupby(["ISOYear", "ISOWeek"], sort=True)

    for (y, w), g in grouped:
        g = g.copy().sort_values("Date")

        # Weekly means
        means = {
            out_name: float(_to_float(g[in_name]).mean())
            for in_name, out_name in cols.items()
        }

        # Season resolution (last known)
        season = g["Season"].dropna().astype(str).iloc[-1] if "Season" in g.columns and g["Season"].notna().any() else ""
        inner = g["InnerSeason"].dropna().astype(str).iloc[-1] if g["InnerSeason"].notna().any() else season

        # High / Low points
        hp = ""
        lp = ""
        if g["Clarity"].notna().any():
            idx = _to_float(g["Clarity"]).idxmax()
            hp = g.loc[idx, "Date"].strftime("%Y-%m-%d")
        if g["StressLevel"].notna().any():
            idx = _to_float(g["StressLevel"]).idxmax()
            lp = g.loc[idx, "Date"].strftime("%Y-%m-%d")

        # Trends vs first day of week
        clarity_trend = "flat"
        stress_trend = "flat"
        first_cl = _to_float(g["Clarity"].iloc[0])
        if pd.notna(first_cl) and pd.notna(means["AvgClarity"]):
            clarity_trend = "up" if means["AvgClarity"] > float(first_cl) else "down" if means["AvgClarity"] < float(first_cl) else "flat"

        first_st = _to_float(g["StressLevel"].iloc[0])
        if pd.notna(first_st) and pd.notna(means["AvgStress"]):
            stress_trend = "up" if means["AvgStress"] > float(first_st) else "down" if means["AvgStress"] < float(first_st) else "flat"

        # Decision mode
        dec_mode = _mode(g["DecisionState"]) if "DecisionState" in g.columns else ""

        # Latest window values (observability only)
        window_vals = {
            "AvgBodyLoadWindow": _latest(g["AvgBodyLoadWindow"]),
            "AvgClarityWindow": _latest(g["AvgClarityWindow"]),
            "AvgStressWindow": _latest(g["AvgStressWindow"]),
            "AvgResonanceWindow": _latest(g["AvgResonanceWindow"]),
            "AvgAmplitudeWindow": _latest(g["AvgAmplitudeWindow"]),
        }

        row = {
            "ISOYear": int(y),
            "ISOWeek": int(w),
            "WeekEnd": _week_end_date(g["Date"]),
            "DaysLogged": int(len(g)),
            "Season": season,
            "InnerSeason": inner,
            **means,
            **window_vals,
            "DecisionState_Mode": dec_mode,
            "HighPoint": hp,
            "LowPoint": lp,
            "ClarityTrend": clarity_trend,
            "StressTrend": stress_trend,
        }

        out_rows.append(row)

    out = pd.DataFrame(out_rows)

    # Schema guarantee
    for c in CANON_COLS:
        if c not in out.columns:
            out[c] = pd.NA

    out = out[CANON_COLS].sort_values(["ISOYear", "ISOWeek"]).reset_index(drop=True)

    # Idempotent canonical write
    out.to_csv(WEEKLY_PATH, index=False)
    print(f"📘 Weekly Signatures rebuilt → {WEEKLY_PATH}")
    print(f"   Weeks: {len(out)}")

# -------------------------------------------------
# Entry point
# -------------------------------------------------
if __name__ == "__main__":
    try:
        build_weekly_signatures()
    except Exception as e:
        print("❌ Error:", e)
        sys.exit(1)
  
