# rhythm_os/oracle/oracle_layer4.py
# SEMANTICS:
# Layer 2 fields (WorldField/HumanField/...) are normalized *decision fields* (0–1),
# used for governance posture and interpretability.
# Layer 4 components (D_*) are *structural stability components* (0–1),
# used to compute DarkField D_t and DarkFieldBand.

"""
Oracle OS — Layer 4 (HFI / Dark Field) — V1.1 (Drop-in Patched)

Role:
    • Infer the latent dark field coherence D(t) from existing Engine fields
    • Summarize Dark Field geometry for each day
    • Persist D_t and its components back into merged_signal.csv
    • Export a compact oracle_layer4.csv for Lighthouse / Sage / Navigator
"""

from __future__ import annotations
from rhythm_os.oracle.validate import validate_oracle_inputs
from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # -> SignalLogic/
DATA_DIR = ROOT / "data"
MERGED_DIR = DATA_DIR / "merged"
MERGED_PATH = MERGED_DIR / "merged_signal.csv"

ORACLE_DIR = DATA_DIR / "oracle"
ORACLE_DIR.mkdir(parents=True, exist_ok=True)
LAYER4_PATH = ORACLE_DIR / "oracle_layer4.csv"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _safe_series(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[name], errors="coerce")


def _safe_last(series: pd.Series, default: float = np.nan) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return default
    return float(s.iloc[-1])


def _clip01(x: float) -> float:
    if x is None or np.isnan(x):
        return np.nan
    return float(max(0.0, min(1.0, x)))


def _nanmean(values) -> float:
    arr = np.array(values, dtype="float64")
    if np.all(np.isnan(arr)):
        return np.nan
    return float(np.nanmean(arr))


def _as_iso_date(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------
# Component computations for D(t)
# ---------------------------------------------------------------------
def _compute_components(window: pd.DataFrame) -> Dict[str, float]:
    """
    Compute the Dark Field components for a rolling window.

    Components:
        • D_HStab       — stability of H_t over the window (low std = stable)
        • D_DriftStab   — stability of HSTResDrift (low mean abs drift = stable)
        • D_MemoryField — memory coherence (MemoryPhaseCoherence preferred)
        • D_GhostField  — ghost stability (GhostStabilityIndex)
        • D_EnvField    — environmental moderation (EnvFactor preferred)
    """

    # ---- H_t stability: low std → high stability ----
    H_series = _safe_series(window, "H_t")
    if H_series.dropna().shape[0] >= 5:
        h_std = float(H_series.std(ddof=0))
        D_HStab = _clip01(1.0 / (1.0 + h_std))
    else:
        D_HStab = np.nan

    # ---- Drift stability: low mean abs drift → high stability ----
    drift_series = _safe_series(window, "HSTResDrift").abs()
    if drift_series.dropna().shape[0] >= 5:
        drift_mean = float(drift_series.mean())
        D_DriftStab = _clip01(1.0 / (1.0 + drift_mean))
    else:
        D_DriftStab = np.nan

    # ---- Memory field fallback chain ----
    mem_phase = _safe_series(window, "MemoryPhaseCoherence")
    if mem_phase.dropna().shape[0] >= 1:
        D_MemoryField = _clip01(_safe_last(mem_phase, default=np.nan))
    else:
        afterglow_eff = _safe_series(window, "AfterglowEff")
        afterglow = _safe_series(window, "Afterglow")
        mem_eff = _safe_series(window, "MemoryChargeEff")
        mem = _safe_series(window, "MemoryCharge")

        if afterglow_eff.dropna().shape[0] >= 1:
            D_MemoryField = _clip01(_safe_last(afterglow_eff, default=np.nan))
        elif afterglow.dropna().shape[0] >= 1:
            D_MemoryField = _clip01(_safe_last(afterglow, default=np.nan))
        elif mem_eff.dropna().shape[0] >= 1:
            D_MemoryField = _clip01(_safe_last(mem_eff, default=np.nan))
        elif mem.dropna().shape[0] >= 1:
            D_MemoryField = _clip01(_safe_last(mem, default=np.nan))
        else:
            D_MemoryField = np.nan

    # ---- Ghost field ----
    ghost_stab = _safe_series(window, "GhostStabilityIndex")
    if ghost_stab.dropna().shape[0] >= 1:
        D_GhostField = _clip01(_safe_last(ghost_stab, default=np.nan))
    else:
        D_GhostField = np.nan

    # ---- Environment field fallback chain ----
    # Preferred: EnvFactor (0..1). Most stable around 0.5.
    env_factor = _safe_series(window, "EnvFactor")
    if env_factor.dropna().shape[0] >= 1:
        v = _safe_last(env_factor, default=np.nan)
        # Stability peak at 0.5: 1 - |x-0.5|*2
        D_EnvField = _clip01(1.0 - abs(v - 0.5) * 2.0) if not np.isnan(v) else np.nan
    else:
        # Fallback: if WVI exists (0..1), stability is (1 - WVI)
        wvi = _safe_series(window, "WVI")
        if wvi.dropna().shape[0] >= 1:
            v = _safe_last(wvi, default=np.nan)
            D_EnvField = _clip01(1.0 - v) if not np.isnan(v) else np.nan
        else:
            # Fallback: EnvPressure (0..1) → stability (1 - EnvPressure)
            env_p = _safe_series(window, "EnvPressure")
            if env_p.dropna().shape[0] >= 1:
                v = _safe_last(env_p, default=np.nan)
                D_EnvField = _clip01(1.0 - v) if not np.isnan(v) else np.nan
            else:
                D_EnvField = 0.5  # neutral if totally absent

    return {
        "D_HStab": D_HStab,
        "D_DriftStab": D_DriftStab,
        "D_MemoryField": D_MemoryField,
        "D_GhostField": D_GhostField,
        "D_EnvField": D_EnvField,
    }


def _dark_field_band(D_t: float) -> str:
    if np.isnan(D_t):
        return "UNKNOWN"
    if D_t >= 0.75:
        return "DEEP"
    if D_t >= 0.55:
        return "COHERENT"
    if D_t >= 0.35:
        return "PARTIAL"
    return "WEAK"


# ---------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------
def _load_merged() -> pd.DataFrame:
    if not MERGED_PATH.exists():
        raise FileNotFoundError(f"merged_signal.csv not found at {MERGED_PATH}")

    df = pd.read_csv(MERGED_PATH, low_memory=False)
    validate_oracle_inputs(df, ctx="ORACLE_L4_INPUT", layer="L4")

    if "Date" not in df.columns:
        raise ValueError("merged_signal.csv missing 'Date' column")

    # Parse and sort for rolling window
    dt = pd.to_datetime(df["Date"], errors="coerce")
    df = (
        df.assign(Date_dt=dt)
        .dropna(subset=["Date_dt"])
        .sort_values("Date_dt")
        .reset_index(drop=True)
    )

    return df


def _compute_dark_field_timeseries(
    df: pd.DataFrame, window_size: int = 60
) -> pd.DataFrame:
    n = len(df)

    D_t_list = []
    bands = []
    D_HStab_list = []
    D_DriftStab_list = []
    D_MemoryField_list = []
    D_GhostField_list = []
    D_EnvField_list = []

    for i in range(n):
        start = max(0, i - window_size + 1)
        window = df.iloc[start : i + 1]

        comps = _compute_components(window)

        D_HStab = comps["D_HStab"]
        D_DriftStab = comps["D_DriftStab"]
        D_MemoryField = comps["D_MemoryField"]
        D_GhostField = comps["D_GhostField"]
        D_EnvField = comps["D_EnvField"]

        D_t = _nanmean([D_HStab, D_DriftStab, D_MemoryField, D_GhostField, D_EnvField])
        D_t = _clip01(D_t) if not np.isnan(D_t) else np.nan
        band = _dark_field_band(D_t)

        D_t_list.append(D_t)
        bands.append(band)
        D_HStab_list.append(D_HStab)
        D_DriftStab_list.append(D_DriftStab)
        D_MemoryField_list.append(D_MemoryField)
        D_GhostField_list.append(D_GhostField)
        D_EnvField_list.append(D_EnvField)

    df["D_t"] = D_t_list
    df["DarkFieldBand"] = bands
    df["D_HStab"] = D_HStab_list
    df["D_DriftStab"] = D_DriftStab_list
    df["D_MemoryField"] = D_MemoryField_list
    df["D_GhostField"] = D_GhostField_list
    df["D_EnvField"] = D_EnvField_list

    return df


def _export_layer4(df: pd.DataFrame) -> None:
    out = pd.DataFrame(
        {
            "Date": df["Date_dt"].dt.strftime("%Y-%m-%d"),
            "D_t": df["D_t"],
            "DarkFieldBand": df["DarkFieldBand"],
            "D_HStab": df["D_HStab"],
            "D_DriftStab": df["D_DriftStab"],
            "D_MemoryField": df["D_MemoryField"],
            "D_GhostField": df["D_GhostField"],
            "D_EnvField": df["D_EnvField"],
        }
    )
    out.to_csv(LAYER4_PATH, index=False)


def _print_dashboard(df: pd.DataFrame) -> None:
    last = df.iloc[-1]

    date_str = pd.to_datetime(last["Date_dt"]).strftime("%Y-%m-%d")
    season = str(last.get("Season", "Unknown"))
    state = str(last.get("SignalState", last.get("State", "N/A")))

    def fmt(x: float) -> str:
        return "nan" if x is None or np.isnan(float(x)) else f"{float(x):.3f}"

    print("══════════════════════════════════════════════")
    print("      🔶 ORACLE OS — LAYER 4 (HFI / DARK)")
    print("══════════════════════════════════════════════")
    print(f" Date:           {date_str}")
    print(f" Season:         {season}")
    print(f" Signal State:   {state}")
    print("----------------------------------------------")
    print(f" D_t (DarkField): {fmt(last.get('D_t', np.nan))}")
    print(f" DarkFieldBand:   {str(last.get('DarkFieldBand', 'UNKNOWN'))}")
    print("----------------------------------------------")
    print(" Component Fields")
    print(" ----------------")
    print(f" H_t Stability:   {fmt(last.get('D_HStab', np.nan))}")
    print(f" Drift Stability: {fmt(last.get('D_DriftStab', np.nan))}")
    print(f" Memory Field:    {fmt(last.get('D_MemoryField', np.nan))}")
    print(f" Ghost Field:     {fmt(last.get('D_GhostField', np.nan))}")
    print(f" Env Field:       {fmt(last.get('D_EnvField', np.nan))}")
    print("══════════════════════════════════════════════")


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
def main() -> None:
    print("📡 Oracle OS — Layer 4 (HFI / Dark Field) starting...")

    df = _load_merged()

    if len(df) < 10:
        print("⚠️ Not enough data points to compute Dark Field. Skipping.\n")
        return

    df = _compute_dark_field_timeseries(df, window_size=60)

    # Write back to merged_signal.csv with Date as ISO string
    df_out = df.drop(columns=["Date_dt"]).copy()
    df_out["Date"] = _as_iso_date(df["Date_dt"])
    df_out.to_csv(MERGED_PATH, index=False)

    # Export Layer 4 view
    _export_layer4(df)

    # Print latest dashboard
    _print_dashboard(df)

    print("\n✅ Oracle Layer 4 updated.")
    print("   → merged_signal.csv with D_t and components")
    print(f"   → {LAYER4_PATH}")


if __name__ == "__main__":
    main()
