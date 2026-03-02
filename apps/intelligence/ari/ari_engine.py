# rhythm_os/ari/ari_engine.py
"""
ARI — Adaptive Rhythmic Intelligence Engine (v1.1.1)

Aligned with:
• Oracle (Dark Field, SignalState)
• Ghost & Memory layers
• Human-safe decision posture

Reads (latest row):
• data/merged/merged_signal.csv
• data/human/human_ledger.csv
• data/human/weekly_signatures.csv
• data/human/tide_state.csv

Writes (idempotent upsert by Date):
• data/human/ari_state.csv
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

MERGED_PATH = DATA / "merged" / "merged_signal.csv"
LEDGER_PATH = DATA / "human" / "human_ledger.csv"
WEEKLY_PATH = DATA / "human" / "weekly_signatures.csv"
TIDE_PATH = DATA / "human" / "tide_state.csv"
ARI_PATH = DATA / "human" / "ari_state.csv"


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def _load_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return None


def _latest(df: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    return df.iloc[-1]


def _safe_float(x, default=None):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def _clip01(x: Optional[float], default=0.5) -> float:
    if x is None:
        return default
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def _fmt(x, d=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "N/A"
    return f"{float(x):.{d}f}"


def normalize_date_str(x: str) -> str:
    """
    Accepts:
      - YYYY-MM-DD
      - YYYY-MM-DD HH:MM:SS
      - DD-MM-YY  (legacy)
    Returns:
      YYYY-MM-DD
    """
    s = str(x).strip()
    if len(s) == 8 and s[2] == "-" and s[5] == "-":
        ts = pd.to_datetime(s, format="%d-%m-%y", errors="coerce")
    else:
        ts = pd.to_datetime(s, errors="coerce")

    if pd.isna(ts):
        raise ValueError(f"Unparseable Date: {x}")

    return ts.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------
def _norm_res(res):  # [-1,1] -> [0,1]
    if res is None:
        return 0.5
    r = max(-1.0, min(1.0, float(res)))
    return _clip01((r + 1.0) / 2.0)


def _norm_amp(a):  # magnitude -> [0,1]
    if a is None:
        return 0.5
    return _clip01(abs(float(a)))


def _norm_dark(d):  # already [0,1]
    return _clip01(d)


def _norm_wvi(w):  # expected [0,1]
    return _clip01(w)


def _norm_energy(e):  # expected [0,1]
    return _clip01(e)


def _norm_clarity(c):  # [1,5] -> [0,1]
    if c is None:
        return 0.5
    c = max(1.0, min(5.0, float(c)))
    return _clip01((c - 1.0) / 4.0)


def _macro_score(state: Optional[str]) -> float:
    if not state:
        return 0.5
    return {
        "CONTRACTING": 0.30,
        "TRANSITION": 0.50,
        "STABLE": 0.60,
        "EXPANDING": 0.80,
        "OVEREXTENDED": 0.20,
    }.get(str(state).upper().strip(), 0.5)


# ---------------------------------------------------------
# CORE ARI
# ---------------------------------------------------------
def run_ari() -> None:
    df_m = _load_csv(MERGED_PATH)
    df_h = _load_csv(LEDGER_PATH)
    df_t = _load_csv(TIDE_PATH)

    world = _latest(df_m)
    human = _latest(df_h)
    tide = _latest(df_t)

    if world is None:
        print("⚠ ARI skipped — merged_signal.csv missing/empty")
        return

    # --- Canonical date key ---
    raw_date = world.get("Date", "")
    date = normalize_date_str(raw_date)

    # --- Extract ---
    res = _safe_float(world.get("ResonanceValue"))
    amp = _safe_float(world.get("Amplitude"))
    d_t = _safe_float(world.get("D_t"))
    dark_band = world.get("DarkFieldBand")
    signal_state = world.get("SignalState")
    streak = _safe_float(world.get("StreakLength"))

    wvi = _safe_float(world.get("WVI"))
    ghost = _safe_float(world.get("GhostStabilityIndex"))

    clarity = _safe_float(human.get("Clarity")) if human is not None else None
    stress = _safe_float(human.get("StressLevel")) if human is not None else None

    energy = _safe_float(tide.get("EnergyWindow")) if tide is not None else None
    macro = tide.get("MacroState") if tide is not None else None

    # --- Normalize ---
    signals: Dict[str, float] = {
        "res": _norm_res(res),
        "amp": _norm_amp(amp),
        "dark": _norm_dark(d_t),
        "clarity": _norm_clarity(clarity),
        "energy": _norm_energy(energy),
        "macro": _macro_score(macro),
        "wvi": _norm_wvi(wvi),
    }

    # --- Weighted index ---
    weights = {
        "res": 0.20,
        "amp": 0.10,
        "dark": 0.20,
        "clarity": 0.20,
        "energy": 0.10,
        "macro": 0.10,
        "wvi": 0.10,
    }

    ari = sum(signals[k] * weights[k] for k in weights)
    ari = _clip01(ari)

    # --- Base decision ---
    if ari < 0.25:
        base = "WAIT"
    elif ari < 0.45:
        base = "PREPARE"
    elif ari < 0.70:
        base = "ACT"
    else:
        base = "PUSH"

    final = base

    # --- Guardrails ---
    if d_t is not None and d_t < 0.35 and final in ("ACT", "PUSH"):
        final = "WAIT"

    if clarity is not None and clarity <= 2 and final in ("ACT", "PUSH"):
        final = "PREPARE"

    if stress is not None and stress >= 4 and final in ("ACT", "PUSH"):
        final = "PREPARE"

    if str(signal_state).strip().lower() == "still" and final == "PUSH":
        final = "ACT"

    # “streak momentum” nudge (optional)
    if streak is not None and streak >= 5 and final == "PREPARE":
        final = "ACT"

    quality = "STABLE" if (ghost is not None and ghost > 0.6) else "MIXED"

    # --- Persist (idempotent upsert by Date) ---
    out = {
        "Date": date,
        "ARIIndex": ari,
        "Decision": final,
        "BaseDecision": base,
        "SignalState": signal_state,
        "DarkFieldBand": dark_band,
        "D_t": d_t,
        "Quality": quality,
    }

    cols = [
        "Date",
        "ARIIndex",
        "Decision",
        "BaseDecision",
        "SignalState",
        "DarkFieldBand",
        "D_t",
        "Quality",
    ]

    if ARI_PATH.exists():
        df_existing = pd.read_csv(ARI_PATH, low_memory=False)
        if "Date" in df_existing.columns:
            df_existing["Date"] = df_existing["Date"].apply(normalize_date_str)
        else:
            df_existing = pd.DataFrame(columns=cols)
    else:
        df_existing = pd.DataFrame(columns=cols)

    # guarantee schema
    for c in cols:
        if c not in df_existing.columns:
            df_existing[c] = pd.NA

    # drop existing row for today then append
    df_existing = df_existing[df_existing["Date"] != date].copy()
    df_new = pd.concat(
        [df_existing, pd.DataFrame([out], columns=cols)], ignore_index=True
    )
    df_new = df_new[cols].sort_values("Date").reset_index(drop=True)

    ARI_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_new.to_csv(ARI_PATH, index=False)

    # --- Console ---
    print("🔺 ARI")
    print(f"   Date:     {date}")
    print(f"   Index:    {_fmt(ari)}")
    print(f"   Decision: {final} (base {base})")
    print(f"   State:    {signal_state}")
    print(f"   Dark:     {dark_band}  D_t={_fmt(d_t)}")
    print(f"   Quality:  {quality}")
    print("")


if __name__ == "__main__":
    run_ari()
