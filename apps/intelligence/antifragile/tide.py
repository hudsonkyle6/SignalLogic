# rhythm_os/antifragile/tide.py
from __future__ import annotations

import sys
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"
LEDGER_PATH = DATA_DIR / "human" / "human_ledger.csv"
WEEKLY_PATH = DATA_DIR / "human" / "weekly_signatures.csv"
TIDE_PATH = DATA_DIR / "human" / "tide_state.csv"


# ---------------------------------------------------------------------
# SAFE LOADERS
# ---------------------------------------------------------------------


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as e:
        print(f"⚠️  Could not read {path}: {e}", file=sys.stderr)
        return pd.DataFrame()


def _to_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _normalize_0_1(x, min_val, max_val) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.5
    if np.isnan(x):
        return 0.5
    if max_val == min_val:
        return 0.5
    return float(np.clip((x - min_val) / (max_val - min_val), 0.0, 1.0))


def _recent_window(
    df: pd.DataFrame, date_col: str, end_date: pd.Timestamp, days: int
) -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df.iloc[0:0].copy()
    if not np.issubdtype(df[date_col].dtype, np.datetime64):
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    start = end_date - timedelta(days=days)
    mask = (df[date_col] <= end_date) & (df[date_col] >= start)
    return df.loc[mask].copy()


def _mean_numeric(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return np.nan
    return float(pd.to_numeric(df[col], errors="coerce").mean())


# ---------------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------------


def run_tide_engine() -> dict:
    print("══════════════════════════════════════")
    print("      🌊 ANTIFRAGILE TIDE ENGINE")
    print("══════════════════════════════════════")
    print(f" Root:        {ROOT}")
    print(f" Ledger:      {LEDGER_PATH}")
    print(f" Weekly log:  {WEEKLY_PATH}")
    print(f" Merged data: {MERGED_PATH}")
    print(f" Tide state:  {TIDE_PATH}")
    print("--------------------------------------")

    weekly = _safe_read_csv(WEEKLY_PATH)
    ledger = _safe_read_csv(LEDGER_PATH)
    merged = _safe_read_csv(MERGED_PATH)

    if merged.empty:
        print("⚠️  merged_signal.csv missing — aborting Tide.")
        return {}

    weekly = _to_dt(weekly, "WeekEnd")
    ledger = _to_dt(ledger, "Date")
    merged = _to_dt(merged, "Date")

    # -----------------------------------------------------------------
    # Reference date (authoritative)
    # -----------------------------------------------------------------
    # Prefer ledger max date (today if logged). Else weekly WeekEnd. Else merged max.
    ref_date = None
    if not ledger.empty and "Date" in ledger.columns:
        ref_date = ledger["Date"].max()
    elif not weekly.empty and "WeekEnd" in weekly.columns:
        ref_date = weekly["WeekEnd"].max()
    elif "Date" in merged.columns:
        ref_date = merged["Date"].max()

    if ref_date is None or pd.isna(ref_date):
        print("⚠️  No valid reference date — aborting Tide.")
        return {}

    date_str = ref_date.date().isoformat()
    print(f" Tide reference date: {date_str}")

    # -----------------------------------------------------------------
    # Human window (CRITICAL FIX): ledger-first for present state
    # -----------------------------------------------------------------
    human_window = pd.DataFrame()
    source = "none"

    if not ledger.empty and "Date" in ledger.columns:
        recent_ledger = _recent_window(ledger, "Date", ref_date, days=7)
        if not recent_ledger.empty:
            human_window = recent_ledger.copy()
            source = "ledger_7d"

    # Fallback to weekly signatures ONLY if ledger insufficient
    if human_window.empty and not weekly.empty and "WeekEnd" in weekly.columns:
        human_window = weekly.sort_values("WeekEnd").tail(4).copy()
        source = "weekly_signatures"

    # Season fields
    season = "Unknown"
    inner_season = "Unknown"

    if source == "ledger_7d":
        if (
            "Season" in human_window.columns
            and not human_window["Season"].dropna().empty
        ):
            season = str(human_window["Season"].dropna().iloc[-1])
        if (
            "InnerSeason" in human_window.columns
            and not human_window["InnerSeason"].dropna().empty
        ):
            inner_season = str(human_window["InnerSeason"].dropna().iloc[-1])
        else:
            inner_season = season
    elif source == "weekly_signatures":
        if (
            "Season" in human_window.columns
            and not human_window["Season"].dropna().empty
        ):
            season = str(human_window["Season"].dropna().iloc[-1])
        if (
            "InnerSeason" in human_window.columns
            and not human_window["InnerSeason"].dropna().empty
        ):
            inner_season = str(human_window["InnerSeason"].dropna().iloc[-1])
        else:
            inner_season = season

    # -----------------------------------------------------------------
    # Human aggregates (these MUST populate now)
    # -----------------------------------------------------------------
    # Support both naming styles if present (weekly uses AvgBodyLoad etc.)
    avg_body = _mean_numeric(human_window, "BodyLoad")
    if np.isnan(avg_body):
        avg_body = _mean_numeric(human_window, "AvgBodyLoad")

    avg_clarity = _mean_numeric(human_window, "Clarity")
    if np.isnan(avg_clarity):
        avg_clarity = _mean_numeric(human_window, "AvgClarity")

    avg_stress = _mean_numeric(human_window, "StressLevel")
    if np.isnan(avg_stress):
        avg_stress = _mean_numeric(human_window, "AvgStress")

    avg_res = _mean_numeric(human_window, "ResonanceValue")
    if np.isnan(avg_res):
        avg_res = _mean_numeric(human_window, "AvgResonance")

    avg_amp = _mean_numeric(human_window, "Amplitude")
    if np.isnan(avg_amp):
        avg_amp = _mean_numeric(human_window, "AvgAmplitude")

    # -----------------------------------------------------------------
    # World aggregates (30d)
    # -----------------------------------------------------------------
    world_30 = _recent_window(merged, "Date", ref_date, 30)
    if world_30.empty:
        print("⚠️  No recent world data in last 30 days — aborting Tide.")
        return {}

    world_res_mean = float(
        pd.to_numeric(world_30.get("ResonanceValue"), errors="coerce").mean()
    )
    world_res_std = float(
        pd.to_numeric(world_30.get("ResonanceValue"), errors="coerce").std(ddof=0)
    )

    world_amp_mean = float(
        pd.to_numeric(world_30.get("Amplitude"), errors="coerce").mean()
    )
    world_amp_std = float(
        pd.to_numeric(world_30.get("Amplitude"), errors="coerce").std(ddof=0)
    )

    drift_mean = (
        float(pd.to_numeric(world_30.get("HSTResDrift"), errors="coerce").mean())
        if "HSTResDrift" in world_30.columns
        else 0.0
    )
    vix_mean = (
        float(pd.to_numeric(world_30.get("VIXClose"), errors="coerce").mean())
        if "VIXClose" in world_30.columns
        else 20.0
    )

    # -----------------------------------------------------------------
    # Normalization
    # -----------------------------------------------------------------
    body_norm = _normalize_0_1(avg_body, 1.0, 5.0)
    stress_norm = _normalize_0_1(avg_stress, 1.0, 5.0)
    clarity_norm = _normalize_0_1(avg_clarity, 1.0, 5.0)

    vol_norm = _normalize_0_1(world_res_std, 0.0, 0.5)
    amp_vol_norm = _normalize_0_1(world_amp_std, 0.0, 0.5)
    drift_norm = _normalize_0_1(abs(drift_mean), 0.0, 0.5)
    vix_norm = _normalize_0_1(vix_mean, 10.0, 40.0)

    seasonal_load_index = float(
        np.mean([body_norm, stress_norm, vol_norm, amp_vol_norm])
    )
    environmental_pressure = float(
        np.mean([vol_norm, amp_vol_norm, drift_norm, vix_norm])
    )
    energy_window = float(
        np.clip(clarity_norm - 0.5 * (body_norm + stress_norm), 0.0, 1.0)
    )

    # -----------------------------------------------------------------
    # Macro State
    # -----------------------------------------------------------------
    if (
        energy_window > 0.6
        and seasonal_load_index < 0.5
        and environmental_pressure < 0.6
    ):
        macro_state = "EXPANDING"
    elif (
        energy_window < 0.3
        or seasonal_load_index > 0.7
        or environmental_pressure > 0.75
    ):
        macro_state = "CONTRACTING"
    else:
        macro_state = "TRANSITION"

    # -----------------------------------------------------------------
    # Final row (CANONICAL)
    # -----------------------------------------------------------------
    out = {
        "Date": date_str,
        "Season": season,
        "InnerSeason": inner_season,
        "SeasonalLoadIndex": seasonal_load_index,
        "EnvironmentalPressure": environmental_pressure,
        "EnergyWindow": energy_window,
        "MacroState": macro_state,
        "AvgBodyLoadWindow": avg_body,
        "AvgClarityWindow": avg_clarity,
        "AvgStressWindow": avg_stress,
        "AvgResonanceWindow": avg_res,
        "AvgAmplitudeWindow": avg_amp,
        "WorldResMean30": world_res_mean,
        "WorldResStd30": world_res_std,
        "WorldAmpMean30": world_amp_mean,
        "WorldAmpStd30": world_amp_std,
        "HSTDriftMean30": drift_mean,
        "VIXMean30": vix_mean,
        "BodyNorm": body_norm,
        "StressNorm": stress_norm,
        "ClarityNorm": clarity_norm,
        "VolNorm": vol_norm,
        "AmpVolNorm": amp_vol_norm,
        "DriftNorm": drift_norm,
        "VIXNorm": vix_norm,
        "Source": source,
    }

    # -----------------------------------------------------------------
    # IDEMPOTENT WRITE (one row per date)
    # -----------------------------------------------------------------
    TIDE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if TIDE_PATH.exists():
        existing = _safe_read_csv(TIDE_PATH)
        if not existing.empty and "Date" in existing.columns:
            existing["Date"] = existing["Date"].astype(str)
            existing = existing[existing["Date"] != date_str].copy()

        # schema-safe append
        tide_df = existing.copy() if not existing.empty else pd.DataFrame()
        for k in out.keys():
            if k not in tide_df.columns:
                tide_df[k] = pd.NA
        tide_df.loc[len(tide_df)] = {c: out.get(c, pd.NA) for c in tide_df.columns}
    else:
        tide_df = pd.DataFrame([out])

    tide_df = tide_df.sort_values("Date").reset_index(drop=True)
    tide_df.to_csv(TIDE_PATH, index=False)

    print("✅ Tide state written →", TIDE_PATH)
    print("══════════════════════════════════════")

    return out


if __name__ == "__main__":
    run_tide_engine()
