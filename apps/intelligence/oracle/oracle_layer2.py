# rhythm_os/oracle/oracle_layer2.py
# SEMANTICS:
# Layer 2 fields (WorldField/HumanField/...) are normalized *decision fields* (0–1),
# used for governance posture and interpretability.
# Layer 4 components (D_*) are *structural stability components* (0–1),
# used to compute DarkField D_t and DarkFieldBand.

"""
ORACLE OS — Layer 2: Harmonic Convergence Field (HCF)

Purpose:
    Combine world signals, memory, ghost, environment, human rhythm,
    and macro tide into a single Harmonic Convergence Field Index (HCFIndex).

Canonical outputs (Layer 2 decision fields):
    - WorldHarmonicField (canonical)  ✅
    - MemoryField
    - GhostField
    - EnvironmentField
    - HumanField
    - MacroTideField
    - G_t
    - HCFIndex, AlignmentBand, AlignmentBias

Logging:
    - Upserts into oracle_layer2.csv (log view)
    - Upserts into oracle_state.csv (canonical wiring)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import math
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"
LEDGER_PATH = DATA_DIR / "human" / "human_ledger.csv"
TIDE_PATH = DATA_DIR / "human" / "tide_state.csv"

ORACLE_DIR = DATA_DIR / "oracle"
ORACLE_DIR.mkdir(parents=True, exist_ok=True)
ORACLE_STATE_PATH = ORACLE_DIR / "oracle_state.csv"
ORACLE_L2_PATH = ORACLE_DIR / "oracle_layer2.csv"


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
    try:
        ts = pd.to_datetime(val, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return None


def _upsert_by_date(
    path: Path, row: Dict[str, Any], date_col: str = "Date"
) -> pd.DataFrame:
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

    # allow schema growth
    for k in row.keys():
        if k not in df.columns:
            df[k] = pd.NA

    mask = df[date_col] == d
    if mask.any():
        idx = df.index[mask][0]
        for k, v in row.items():
            df.at[idx, k] = v
    else:
        df.loc[len(df)] = {c: row.get(c, pd.NA) for c in df.columns}

    df.to_csv(path, index=False)
    return df


def safe_get(row: pd.Series, col: str, default=None):
    if row is None:
        return default
    if col not in row.index:
        return default
    v = row[col]
    return v if pd.notna(v) else default


def clamp01(x) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.5
    if math.isnan(v):
        return 0.5
    return max(0.0, min(1.0, v))


def normalize_from_5(x, invert=False) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.5
    if math.isnan(v):
        return 0.5
    v = max(1.0, min(5.0, v))
    norm = (v - 1.0) / 4.0
    return 1.0 - norm if invert else norm


def macro_state_score(macro_state: str | None) -> float:
    """
    Align to Tide Engine outputs:
        EXPANDED / CONTRACTING / TRANSITION
    Accept EXPANDING as synonym for EXPANDED.
    """
    if not isinstance(macro_state, str):
        return 0.5
    s = macro_state.upper().strip()
    if s in ("EXPANDED", "EXPANDING"):
        return 1.0
    if s == "TRANSITION":
        return 0.60
    if s == "CONTRACTING":
        return 0.30
    return 0.5


# ---------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------


def build_world_harmonic_field(row: pd.Series) -> float:
    H_t = clamp01(safe_get(row, "H_t", 0.5))
    G_t = clamp01(safe_get(row, "G_t", 0.5))
    res = clamp01(safe_get(row, "ResonanceValue", 0.5))

    drift = safe_get(row, "HSTResDrift", 0.0)
    phase_div = safe_get(row, "HSTPhaseDiv", 0.0)

    try:
        drift_penalty = 1.0 - min(abs(float(drift)), 1.0)
    except Exception:
        drift_penalty = 0.5

    try:
        phase = float(phase_div)
        phase_norm = min(abs(phase) / math.pi, 1.0)
        phase_penalty = 1.0 - phase_norm
    except Exception:
        phase_penalty = 0.5

    base = 0.55 * H_t + 0.25 * G_t + 0.20 * res
    world = base * (0.60 + 0.20 * drift_penalty + 0.20 * phase_penalty)
    return clamp01(world)


def build_memory_field(row: pd.Series) -> float:
    mem_eff = safe_get(row, "MemoryChargeEff", None)
    ag_eff = safe_get(row, "AfterglowEff", None)
    if mem_eff is None:
        mem_eff = safe_get(row, "MemoryCharge", 0.5)
    if ag_eff is None:
        ag_eff = safe_get(row, "Afterglow", 0.5)
    return clamp01(0.5 * clamp01(mem_eff) + 0.5 * clamp01(ag_eff))


def build_ghost_field(row: pd.Series) -> float:
    stab = clamp01(safe_get(row, "GhostStabilityIndex", 0.5))
    instab = safe_get(row, "GhostInstabilitySmooth", None)
    gov = clamp01(safe_get(row, "GhostGovernor", 0.5))

    try:
        instab_norm = clamp01(float(instab))
        instab_penalty = 1.0 - instab_norm
    except Exception:
        instab_penalty = 0.5

    ghost_core = 0.60 * stab + 0.40 * gov
    ghost = ghost_core * (0.70 + 0.30 * instab_penalty)
    return clamp01(ghost)


def build_environment_field(row: pd.Series) -> float:
    WVI = clamp01(safe_get(row, "WVI", 0.5))
    env_factor = clamp01(safe_get(row, "EnvFactor", 0.5))
    stability = 1.0 - WVI
    return clamp01(0.5 * stability + 0.5 * env_factor)


def build_human_field(ledger_last: Optional[pd.Series]) -> float:
    if ledger_last is None:
        return 0.5
    clarity = normalize_from_5(safe_get(ledger_last, "Clarity", 3))
    stress = normalize_from_5(safe_get(ledger_last, "StressLevel", 3), invert=True)
    return clamp01(0.60 * clarity + 0.40 * stress)


def build_macro_tide_field(tide_last: Optional[pd.Series]) -> float:
    if tide_last is None:
        return 0.5
    macro = macro_state_score(safe_get(tide_last, "MacroState", None))
    energy = clamp01(safe_get(tide_last, "EnergyWindow", 0.5))
    return clamp01(0.60 * macro + 0.40 * energy)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def run_oracle_layer2():
    if not MERGED_PATH.exists():
        print("⚠ ORACLE L2: merged_signal.csv not found.")
        return

    df = pd.read_csv(MERGED_PATH)
    if df.empty:
        print("⚠ ORACLE L2: merged_signal.csv is empty.")
        return

    # Normalize Date ordering
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    latest = df.iloc[-1]
    date = _to_iso_date(safe_get(latest, "Date", None))
    season = safe_get(latest, "Season", "N/A")
    state = safe_get(latest, "SignalState", safe_get(latest, "State", "N/A"))

    # Human ledger last
    ledger_last = None
    df_ledger = _read_csv_safe(LEDGER_PATH)
    if not df_ledger.empty and "Date" in df_ledger.columns:
        df_ledger["Date"] = pd.to_datetime(df_ledger["Date"], errors="coerce")
        df_ledger = df_ledger.dropna(subset=["Date"]).sort_values("Date")
        ledger_last = df_ledger.iloc[-1] if not df_ledger.empty else None

    # Tide last
    tide_last = None
    df_tide = _read_csv_safe(TIDE_PATH)
    if not df_tide.empty and "Date" in df_tide.columns:
        df_tide["Date"] = pd.to_datetime(df_tide["Date"], errors="coerce")
        df_tide = df_tide.dropna(subset=["Date"]).sort_values("Date")
        tide_last = df_tide.iloc[-1] if not df_tide.empty else None

    # Component fields
    world_field = build_world_harmonic_field(latest)  # ✅ canonical field
    memory = build_memory_field(latest)
    ghost = build_ghost_field(latest)
    env = build_environment_field(latest)
    human = build_human_field(ledger_last)
    macro = build_macro_tide_field(tide_last)
    G_t = clamp01(safe_get(latest, "G_t", 0.5))

    # Weights (world-heavy but balanced)
    w_world = 0.25
    w_memory = 0.15
    w_ghost = 0.15
    w_env = 0.15
    w_human = 0.15
    w_macro = 0.10
    w_G = 0.05
    total = w_world + w_memory + w_ghost + w_env + w_human + w_macro + w_G
    w_world, w_memory, w_ghost, w_env, w_human, w_macro, w_G = [
        w / total for w in (w_world, w_memory, w_ghost, w_env, w_human, w_macro, w_G)
    ]

    HCF = clamp01(
        w_world * world_field
        + w_memory * memory
        + w_ghost * ghost
        + w_env * env
        + w_human * human
        + w_macro * macro
        + w_G * G_t
    )

    # Bands / bias
    if HCF >= 0.70:
        band = "CONVERGENT"
    elif HCF >= 0.40:
        band = "PARTIAL"
    else:
        band = "DIVERGENT"

    diff = world_field - human
    if diff > 0.15:
        bias = "WORLD-LED"
    elif diff < -0.15:
        bias = "HUMAN-LED"
    else:
        bias = "BALANCED"

    # Canonical Layer-2 row
    out_row = {
        "Date": date,
        "Season": season,
        "SignalState": state,
        "HCFIndex": HCF,
        "AlignmentBand": band,
        "AlignmentBias": bias,
        # ✅ canonical name expected by your tables
        "WorldHarmonicField": world_field,
        # ✅ backward-compatible alias (safe to keep)
        "WorldHarmonic": world_field,
        "MemoryField": memory,
        "GhostField": ghost,
        "EnvironmentField": env,
        "HumanField": human,
        "MacroTideField": macro,
        "G_t": G_t,
    }

    # Write log + canonical state
    _upsert_by_date(ORACLE_L2_PATH, out_row, date_col="Date")
    _upsert_by_date(ORACLE_STATE_PATH, out_row, date_col="Date")

    print("══════════════════════════════════════")
    print("     🔶 ORACLE OS — LAYER 2 (HCF)")
    print("══════════════════════════════════════")
    print(f" Date:           {date}")
    print(f" Season:         {season}")
    print(f" Signal State:   {state}")
    print("--------------------------------------")
    print(f" HCF Index:      {HCF:.3f}")
    print(f" Alignment Band: {band}")
    print(f" Alignment Bias: {bias}")
    print("--------------------------------------")
    print(f" World Field:    {world_field:.3f}")
    print(f" Memory Field:   {memory:.3f}")
    print(f" Ghost Field:    {ghost:.3f}")
    print(f" Env Field:      {env:.3f}")
    print(f" Human Field:    {human:.3f}")
    print(f" Macro Tide:     {macro:.3f}")
    print(f" G_t:            {G_t:.3f}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    run_oracle_layer2()
