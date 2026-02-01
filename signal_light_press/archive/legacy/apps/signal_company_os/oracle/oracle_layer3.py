# rhythm_os/oracle/oracle_layer3.py
"""
Oracle OS — Layer 3 (Horizon Layer)

Role:
    • Read latest oracle_state.csv (now correctly wired with L1 + L2 fields)
    • Compute Oracle Horizon Index (OHI)
    • Classify horizon band/bias + short/long windows
    • Upsert results back into oracle_state.csv (by Date)

Pure read/derive/write. Does not touch core engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

ORACLE_DIR = DATA / "oracle"
ORACLE_STATE_PATH = ORACLE_DIR / "oracle_state.csv"
TIDE_PATH = DATA / "human" / "tide_state.csv"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _to_iso_date(val) -> Optional[str]:
    if val is None:
        return None
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def _upsert_by_date(path: Path, row: Dict[str, Any], date_col: str = "Date") -> pd.DataFrame:
    df = _read_csv_safe(path)
    d = _to_iso_date(row.get(date_col))
    if d is None:
        raise ValueError("Row has no valid Date for upsert.")
    row[date_col] = d

    if df.empty:
        out = pd.DataFrame([row])
        out.to_csv(path, index=False)
        return out

    if date_col not in df.columns:
        df[date_col] = pd.NA

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

    for k in row.keys():
        if k not in df.columns:
            df[k] = pd.NA

    mask = (df[date_col] == d)
    if mask.any():
        idx = df.index[mask][0]
        for k, v in row.items():
            df.at[idx, k] = v
    else:
        df.loc[len(df)] = {c: row.get(c, pd.NA) for c in df.columns}

    df.to_csv(path, index=False)
    return df


def _safe_get(row: Optional[pd.Series], key: str, default=None):
    if row is None:
        return default
    if key not in row.index:
        return default
    v = row[key]
    return default if pd.isna(v) else v


def _normalize01(v) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.5
    if np.isnan(x):
        return 0.5
    return float(max(0.0, min(1.0, x)))


def _macro_window_from_state(macro_state: str) -> float:
    """
    Match Tide Engine outputs:
      EXPANDED / CONTRACTING / TRANSITION
    """
    if not isinstance(macro_state, str):
        return 0.5
    s = macro_state.upper().strip()
    if s in ("EXPANDED", "EXPANDING"):
        return 0.80
    if s == "TRANSITION":
        return 0.55
    if s == "CONTRACTING":
        return 0.25
    return 0.5


def _classify_band(ohi: float) -> str:
    if ohi < 0.33:
        return "NARROW"
    if ohi < 0.66:
        return "MODERATE"
    return "WIDE"


def _classify_bias(ohi: float, risk: float) -> str:
    if ohi >= 0.66 and risk <= 0.40:
        return "FAVORABLE"
    if ohi <= 0.33 and risk >= 0.60:
        return "CAUTION"
    return "BALANCED"


def _classify_windows(ohi: float, macro_open: float) -> Tuple[str, str]:
    # short horizon
    if ohi >= 0.70 and macro_open >= 0.60:
        short = "OPEN"
    elif ohi <= 0.30 or macro_open <= 0.30:
        short = "CLOSED"
    else:
        short = "GUARDED"

    # long horizon (leans more on macro openness)
    if macro_open >= 0.70:
        long = "WIDENING"
    elif macro_open <= 0.30:
        long = "NARROWING"
    else:
        long = "STEADY"

    return short, long


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def run_oracle_layer3() -> None:
    print("══════════════════════════════════════")
    print("   🔭 ORACLE OS — LAYER 3 (HORIZON)")
    print("══════════════════════════════════════")

    oracle_df = _read_csv_safe(ORACLE_STATE_PATH)
    if oracle_df.empty:
        print(f"[L3] WARNING: oracle_state.csv missing/empty at {ORACLE_STATE_PATH}")
        return

    # Normalize oracle Date and take latest
    if "Date" in oracle_df.columns:
        oracle_df["Date"] = pd.to_datetime(oracle_df["Date"], errors="coerce")
        oracle_df = oracle_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    row = oracle_df.iloc[-1]
    date = _to_iso_date(_safe_get(row, "Date", None)) or "N/A"
    season = _safe_get(row, "Season", "N/A")
    signal_state = _safe_get(row, "SignalState", "N/A")

    # Pull L1 + L2 (wired) fields
    oci = _normalize01(_safe_get(row, "OracleConvergenceIndex", 0.5))
    risk = _normalize01(_safe_get(row, "OracleRiskIndex", 0.5))
    hcf = _normalize01(_safe_get(row, "HCFIndex", 0.5))

    world = _normalize01(_safe_get(row, "WorldHarmonicField", 0.5))
    mem = _normalize01(_safe_get(row, "MemoryField", 0.5))
    ghost = _normalize01(_safe_get(row, "GhostField", 0.5))
    env = _normalize01(_safe_get(row, "EnvironmentField", 0.5))
    human = _normalize01(_safe_get(row, "HumanField", 0.5))
    macro_field = _normalize01(_safe_get(row, "MacroTideField", 0.5))

    # Macro openness (prefer tide_state, fallback to macro_field)
    macro_state = "UNKNOWN"
    macro_open = 0.5
    tide_df = _read_csv_safe(TIDE_PATH)
    if not tide_df.empty and "Date" in tide_df.columns:
        tide_df["Date"] = pd.to_datetime(tide_df["Date"], errors="coerce")
        tide_df = tide_df.dropna(subset=["Date"]).sort_values("Date")

        # Use the closest tide row <= oracle date
        try:
            target = pd.to_datetime(date)
            tide_df = tide_df[tide_df["Date"] <= target]
            if not tide_df.empty:
                trow = tide_df.iloc[-1]
                macro_state = str(_safe_get(trow, "MacroState", "UNKNOWN"))
                macro_open = _macro_window_from_state(macro_state)
        except Exception:
            pass

    macro_combined = 0.5 * macro_field + 0.5 * macro_open

    # Multi-field blend
    multi = float(np.mean([world, env, human, ghost, mem, macro_combined]))

    # Oracle Horizon Index (OHI)
    ohi = float(max(min(0.40 * oci + 0.30 * hcf + 0.30 * multi, 1.0), 0.0))

    band = _classify_band(ohi)
    bias = _classify_bias(ohi, risk)
    w_short, w_long = _classify_windows(ohi, macro_combined)

    # Upsert horizon fields into oracle_state.csv
    out = {
        "Date": date,
        "OracleHorizonIndex": ohi,
        "OracleHorizonBand": band,
        "OracleHorizonBias": bias,
        "HorizonWindowShort": w_short,
        "HorizonWindowLong": w_long,
        "HorizonMacroState": macro_state,
    }
    _upsert_by_date(ORACLE_STATE_PATH, out, date_col="Date")

    # Console output
    print(f"   Date:           {date}")
    print(f"   Season:         {season}")
    print(f"   Signal State:   {signal_state}")
    print("--------------------------------------")
    print(f"   Horizon Index:  {ohi:.3f}")
    print(f"   Horizon Band:   {band}")
    print(f"   Horizon Bias:   {bias}")
    print("--------------------------------------")
    print(f"   Short Window:   {w_short}")
    print(f"   Long Window:    {w_long}")
    print(f"   Macro State:    {macro_state}")
    print("--------------------------------------")
    print(f"   OCI (L1):       {oci:.3f}")
    print(f"   HCF (L2):       {hcf:.3f}")
    print(f"   WorldField:     {world:.3f}")
    print(f"   HumanField:     {human:.3f}")
    print(f"   EnvField:       {env:.3f}")
    print(f"   GhostField:     {ghost:.3f}")
    print(f"   MemoryField:    {mem:.3f}")
    print(f"   MacroCombined:  {macro_combined:.3f}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    run_oracle_layer3()

