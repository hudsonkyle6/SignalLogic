# rhythm_os/core/hst/hst_shadow_tools.py
"""
HST Shadow Tools — V1.1

Role:
    • Read latest HST shadow columns from merged_signal.csv
    • Validate A_t, C_t, E_t, H_t, phi_h, phi_e
    • Render a clear HST Shadow Dashboard (console only)
    • No mutation of data, no writes — read-only lens.

This is a *presentation* + sanity tool for the Engine Room.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]  # -> SignalLogic/
DATA_DIR = ROOT / "data"
MERGED_DIR = DATA_DIR / "merged"
MERGED_PATH = MERGED_DIR / "merged_signal.csv"


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class HSTSnapshot:
    date: pd.Timestamp
    season: str
    state: str
    resonance: float

    A_t: float
    C_t: float
    E_t: float
    H_t: float
    phi_h: float
    phi_e: float


# ---------------------------------------------------------------------
# Helpers — sparkline + basic stats
# ---------------------------------------------------------------------

def _sparkline(values, width: int = 12) -> str:
    clean = [float(v) for v in values if pd.notna(v)]
    if not clean:
        return " " * width

    blocks = "▁▂▃▄▅▆▇█"
    mn, mx = min(clean), max(clean)
    if mx == mn:
        return blocks[0] * min(len(clean), width)

    out = []
    for v in clean[-width:]:
        n = (v - mn) / (mx - mn) if mx != mn else 0.0
        idx = int(max(0, min(n * (len(blocks) - 1), len(blocks) - 1)))
        out.append(blocks[idx])

    return "".join(out)


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if pd.isna(val):
            return default
        return float(val)
    except Exception:
        return default


def _resonance_state_label(v: float) -> str:
    if v >= 0.5:
        return "Resonant"
    if v <= -0.5:
        return "Turbulent"
    return "Still"


# ---------------------------------------------------------------------
# Label logic for HST metrics
# ---------------------------------------------------------------------

def _label_H(H_t: float) -> str:
    if H_t > 1.2:
        return "Strong"
    if H_t > 0.8:
        return "Moderate"
    if H_t > 0.4:
        return "Weak"
    return "Collapsed"


def _label_A(A_t: float) -> str:
    if A_t > 0.66:
        return "High"
    if A_t > 0.33:
        return "Moderate"
    return "Low"


def _label_C(C_t: float) -> str:
    if C_t >= 2.0:
        return "High"
    if C_t >= 1.0:
        return "Moderate"
    return "Low"


def _label_E(E_t: float) -> str:
    if E_t > 1.0:
        return "High"
    if E_t > 0.5:
        return "Moderate"
    return "Low"


def _trend_label(series: pd.Series, window: int = 7) -> Tuple[float, str]:
    """
    Compute simple linear slope over last `window` points and map → label.
    Returns (slope, label).
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 3:
        return 0.0, "Insufficient data"

    tail = s.tail(window)
    if len(tail) < 3:
        return 0.0, "Insufficient data"

    y = tail.to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)

    try:
        slope, _ = np.polyfit(x, y, 1)
    except Exception:
        return 0.0, "Unreadable"

    if slope > 0.02:
        return float(slope), "Rising"
    if slope < -0.02:
        return float(slope), "Falling"
    return float(slope), "Steady"


# ---------------------------------------------------------------------
# Load + snapshot extraction
# ---------------------------------------------------------------------

def _load_merged() -> pd.DataFrame:
    if not MERGED_PATH.exists():
        raise FileNotFoundError(f"merged_signal.csv not found at {MERGED_PATH}")

    df = pd.read_csv(MERGED_PATH)
    if "Date" not in df.columns:
        raise ValueError("merged_signal.csv missing 'Date' column")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def _latest_snapshot(df: pd.DataFrame) -> HSTSnapshot:
    required_cols = [
        "Season", "SignalState", "ResonanceValue",
        "A_t", "C_t", "E_t", "H_t", "phi_h", "phi_e",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"merged_signal.csv missing required column: {col}")

    row = df.iloc[-1]

    date = row["Date"]
    season = str(row.get("Season", "Unknown"))
    state = str(row.get("SignalState", _resonance_state_label(_safe_float(row.get("ResonanceValue", 0.0)))))
    resonance = _safe_float(row.get("ResonanceValue", 0.0))

    return HSTSnapshot(
        date=date,
        season=season,
        state=state,
        resonance=resonance,
        A_t=_safe_float(row.get("A_t", 0.0)),
        C_t=_safe_float(row.get("C_t", 1.0)),
        E_t=_safe_float(row.get("E_t", 0.0)),
        H_t=_safe_float(row.get("H_t", 0.0)),
        phi_h=_safe_float(row.get("phi_h", 0.0)),
        phi_e=_safe_float(row.get("phi_e", 0.0)),
    )


# ---------------------------------------------------------------------
# Validation table (kept from earlier version, but now optional)
# ---------------------------------------------------------------------

def _validate_hst_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["A_t", "C_t", "E_t", "H_t", "phi_h", "phi_e"]
    records = []
    for col in cols:
        if col not in df.columns:
            records.append({
                "Column": col,
                "Exists": False,
                "NaNs": "N/A",
                "Infs": "N/A",
                "Min": "N/A",
                "Max": "N/A",
                "Notes": "MISSING COLUMN",
            })
            continue

        s = pd.to_numeric(df[col], errors="coerce")
        exists = True
        n_nans = int(s.isna().sum())
        n_infs = int(np.isinf(s).sum())
        if s.dropna().empty:
            min_val = max_val = "N/A"
        else:
            min_val = float(s.min())
            max_val = float(s.max())

        notes = "OK"
        if col in ("phi_h", "phi_e"):
            # expected [0, 2π], but we allow wrapped negatives in this phase
            bad = ((s.dropna() < -np.pi) | (s.dropna() > np.pi)).sum()
            if bad > 0:
                notes = f"{bad} phase values out of [-π, π]"

        records.append({
            "Column": col,
            "Exists": exists,
            "NaNs": n_nans,
            "Infs": n_infs,
            "Min": min_val,
            "Max": max_val,
            "Notes": notes,
        })

    return pd.DataFrame(records)


def _print_validation_table(df_valid: pd.DataFrame) -> None:
    print("📡 HST SHADOW VALIDATION REPORT — LATEST STATUS")
    print(f"{'Column':>6}  {'Exists':>6}  {'NaNs':>4}  {'Infs':>4}  {'Min':>9} {'Max':>9}  Notes")
    for _, row in df_valid.iterrows():
        col = row["Column"]
        exists = row["Exists"]
        n_nans = row["NaNs"]
        n_infs = row["Infs"]
        mn = row["Min"]
        mx = row["Max"]
        notes = row["Notes"]

        print(
            f"{col:>6}  "
            f"{str(exists):>6}  "
            f"{str(n_nans):>4}  "
            f"{str(n_infs):>4}  "
            f"{str(mn):>9} {str(mx):>9}  {notes}"
        )
    print()


# ---------------------------------------------------------------------
# HST Shadow Dashboard Renderer
# ---------------------------------------------------------------------

def _print_hst_shadow_dashboard(df: pd.DataFrame, snap: HSTSnapshot) -> None:
    """
    Pretty, read-only HST dashboard for the latest day.
    """

    # 7-day trend for H_t
    H_series = pd.to_numeric(df["H_t"], errors="coerce")
    slope, trend_label = _trend_label(H_series, window=7)
    spark = _sparkline(H_series.tail(12).tolist(), width=24)

    # Labels
    H_label = _label_H(snap.H_t)
    A_label = _label_A(snap.A_t)
    C_label = _label_C(snap.C_t)
    E_label = _label_E(snap.E_t)

    date_str = snap.date.strftime("%Y-%m-%d")

    print("════════════════════════════════════════════════════════════")
    print("                 📡 SIGNAL ENGINE — HST SHADOW")
    print("════════════════════════════════════════════════════════════")
    print(f"  Date:       {date_str}")
    print(f"  Season:     {snap.season}")
    print(f"  State:      {snap.state}")
    print(f"  Resonance:  {snap.resonance:.2f}")
    print("────────────────────────────────────────────────────────────")
    print("  HARMONIC OUTPUT (H_t)")
    print("────────────────────────────────────────────────────────────")
    print(f"  H_t:         {snap.H_t:.3f}   ({H_label})")
    print(f"  ΔH_t (7d):   {slope:+.3f}   ({trend_label})")
    print(f"  7-Day Spark: {spark}")
    print("────────────────────────────────────────────────────────────")
    print("  ALIGNMENT (A_t)")
    print("────────────────────────────────────────────────────────────")
    print(f"  Alignment:   {snap.A_t:.3f}   ({A_label})")
    print(f"  Phase (φ_h): {snap.phi_h:+.3f} rad")
    print("────────────────────────────────────────────────────────────")
    print("  SYSTEM CAPACITY (C_t)")
    print("────────────────────────────────────────────────────────────")
    print(f"  Capacity:    {snap.C_t:.3f}   ({C_label})")
    print("  Context:     Energy available for coherent behavior.")
    print("────────────────────────────────────────────────────────────")
    print("  ENVIRONMENTAL FIELD (E_t)")
    print("────────────────────────────────────────────────────────────")
    print(f"  Ext. Energy: {snap.E_t:.3f}   ({E_label})")
    print(f"  Phase (φ_e): {snap.phi_e:+.3f} rad")
    print("════════════════════════════════════════════════════════════")
    print()


# ---------------------------------------------------------------------
# Narrative summary (simple, based on A_t / C_t / E_t / H_t)
# ---------------------------------------------------------------------

def _narrative_summary(snap: HSTSnapshot) -> str:
    H_label = _label_H(snap.H_t)
    A_label = _label_A(snap.A_t)
    C_label = _label_C(snap.C_t)
    E_label = _label_E(snap.E_t)

    # Simple rules, can be refined later
    if H_label in ("Strong", "Moderate") and A_label in ("High", "Moderate"):
        return ("Today’s harmonic output is "
                f"{H_label.lower()}. Alignment is {A_label.lower()}, "
                f"capacity is {C_label.lower()}, and the external field reads {E_label.lower()}. "
                "Overall: a coherent environment with usable alignment.")
    if H_label == "Collapsed":
        return ("Today’s harmonic output is collapsed. Alignment and capacity must be read "
                "with caution; the external field reads "
                f"{E_label.lower()}. Overall: a disrupted environment — move slowly.")
    if A_label == "Low":
        return ("Today’s harmonic output is mixed. Alignment is low, even though capacity is "
                f"{C_label.lower()} and the external field reads {E_label.lower()}. "
                "Overall: energy without agreement — expect crosscurrents.")

    return ("Today’s harmonic output is moderate. Alignment, capacity, and external energy "
            "sit in a middle band. Overall: a neutral harmonic environment with modest alignment.")


def _print_narrative(snap: HSTSnapshot) -> None:
    print("📜 HST SHADOW INTERPRETATION — DAILY SUMMARY")
    print(_narrative_summary(snap))
    print()


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------

def main() -> None:
    print("📡 Running HST Shadow Tools...\n")

    df = _load_merged()

    # 1) Validation table
    valid_df = _validate_hst_columns(df)
    _print_validation_table(valid_df)

    # If any required column is missing, stop after validation
    if not all(valid_df[valid_df["Column"].isin(["A_t", "C_t", "E_t", "H_t", "phi_h", "phi_e"])]["Exists"]):
        print("⚠️ Required HST columns missing — dashboard not rendered.\n")
        return

    # 2) Latest snapshot + dashboard
    snap = _latest_snapshot(df)
    _print_hst_shadow_dashboard(df, snap)

    # 3) Narrative
    _print_narrative(snap)


if __name__ == "__main__":
    main()
