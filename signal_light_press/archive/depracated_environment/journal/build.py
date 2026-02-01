"""
Journal Engine — build.py (V3, HST aligned)

Rebuilds signal_journal.csv fully from merged_signal.csv.

This is the canonical journal constructor for Rhythm OS:
- Uses merged_signal.csv as the single source of truth
- Copies all HST fields directly from merged (A_t, C_t, E_t, H_t, phi_h, phi_e,
  HSTResDrift, HSTAmpCorr, HSTTempCorr, HSTPhaseDiv)
- Copies Amplitude and MoonAge when present
- Copies Coupling, Memory, Ghost, Environment fields when present
- Computes PrevState / ChangeType / StreakLength over the whole history
- Uses Phase from merged if present, otherwise derives a fallback from ResonanceValue.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]  # -> SignalLogic/
DATA_DIR = ROOT / "data"
MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"
JOURNAL_PATH = DATA_DIR / "journal" / "signal_journal.csv"

# Required columns the engine guarantees in merged_signal.csv
REQUIRED_COLS = [
    "Date",
    "Season",
    "SignalState",
    "ResonanceValue",
    "SP500Close",
    "VIXClose",
    "TempAvg",
    "MoonIllum",
    "A_t",
    "C_t",
    "E_t",
    "H_t",
    "phi_h",
    "phi_e",
]


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _load_merged() -> pd.DataFrame:
    """Load merged_signal.csv, normalize Date, validate required columns."""
    if not MERGED_PATH.exists():
        raise FileNotFoundError(
            f"Cannot find merged_signal.csv at {MERGED_PATH}\n"
            f"→ Run the kernel or merge_signals + resonance_score first."
        )

    df = pd.read_csv(MERGED_PATH)
    df.columns = [c.strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "merged_signal.csv is missing required columns:\n"
            f"  {missing}\n"
            "Run full kernel pipeline (or resonance_score) to ensure merged_signal "
            "has all canonical fields."
        )

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df["Date"] = df["Date"].dt.date

    return df


def _map_phase_from_res(res_value: float) -> str:
    """Fallback phase classification when merged has no Phase column."""
    if pd.isna(res_value):
        return "Oscillating"
    if res_value >= 0.66:
        return "Emerging"
    if res_value >= 0.25:
        return "Consolidating"
    if res_value > -0.25:
        return "Oscillating"
    if res_value > -0.66:
        return "Decaying"
    return "Anomalous"


def _compute_dynamics(journal: pd.DataFrame) -> pd.DataFrame:
    """
    Compute PrevState, ChangeType, and StreakLength over the ordered journal.
    Assumes journal is sorted ascending by Date.
    """
    prev_states = []
    changes = []
    streaks = []

    prev_state = ""
    prev_streak = 0

    for i, row in journal.iterrows():
        curr_state = row["SignalState"]

        # PrevState
        if i == 0:
            prev_states.append("")
        else:
            prev_states.append(prev_state)

        # ChangeType
        if i == 0:
            change = "New"
        else:
            if curr_state == prev_state:
                change = "Continue"
            else:
                if curr_state == "Resonant" and prev_state != "Resonant":
                    change = "Rise"
                elif curr_state == "Turbulent" and prev_state != "Turbulent":
                    change = "Fall"
                else:
                    change = "Flip"
        changes.append(change)

        # StreakLength
        if i == 0:
            streak = 1
        else:
            streak = prev_streak + 1 if curr_state == prev_state else 1
        streaks.append(streak)

        prev_state = curr_state
        prev_streak = streak

    journal["PrevState"] = prev_states
    journal["ChangeType"] = changes
    journal["StreakLength"] = streaks

    return journal


# -------------------------------------------------------------------
# Rebuild Journal
# -------------------------------------------------------------------

def rebuild_journal() -> None:
    print("📘 Rebuilding Signal Journal v3 from merged_signal.csv...")

    merged = _load_merged()

    # Phase: copy from merged if available, else derive from ResonanceValue
    if "Phase" in merged.columns:
        phase_series = merged["Phase"]
    else:
        phase_series = merged["ResonanceValue"].apply(_map_phase_from_res)

    # Optional fields from merged (use .get so we can gracefully fallback)
    moon_age = merged.get("MoonAge", pd.NA)
    amplitude = merged.get("Amplitude", pd.NA)

    hst_res_drift = merged.get("HSTResDrift", pd.NA)
    hst_amp_corr = merged.get("HSTAmpCorr", pd.NA)
    hst_temp_corr = merged.get("HSTTempCorr", pd.NA)
    hst_phase_div = merged.get("HSTPhaseDiv", pd.NA)

    # Coupling metrics (now written by coupling engine)
    coupling_col = merged.get("CouplingCol", "")
    coupling_lag = merged.get("CouplingLag", "")
    coupling_pearson = merged.get("CouplingPearson", "")
    amp_coupling_col = merged.get("AmpCouplingCol", "")
    amp_coupling_lag = merged.get("AmpCouplingLag", "")
    amp_coupling_pearson = merged.get("AmpCouplingPearson", "")

    # Memory / Ghost / Environment fields
    event_intensity = merged.get("EventIntensity", pd.NA)
    memory_charge = merged.get("MemoryCharge", pd.NA)
    afterglow = merged.get("Afterglow", pd.NA)
    memory_phase = merged.get("MemoryPhase", pd.NA)
    memory_drift = merged.get("MemoryDrift", pd.NA)
    memory_phase_coh = merged.get("MemoryPhaseCoherence", pd.NA)
    ghost_level = merged.get("GhostLevel", pd.NA)
    ghost_stability = merged.get("GhostStabilityIndex", pd.NA)
    wvi = merged.get("WVI", pd.NA)
    env_pressure = merged.get("EnvPressure", pd.NA)
    env_factor = merged.get("EnvFactor", pd.NA)

    # Base journal frame
    journal = pd.DataFrame(
        {
            "Date": merged["Date"],
            "Season": merged["Season"],
            "SignalState": merged["SignalState"],
            "ResonanceValue": merged["ResonanceValue"],
            "Phase": phase_series,
            "SP500Close": merged["SP500Close"],
            "VIXClose": merged["VIXClose"],
            "TempAvg": merged["TempAvg"],
            "MoonIllum": merged["MoonIllum"],
            "CouplingCol": coupling_col,
            "CouplingLag": coupling_lag,
            "CouplingPearson": coupling_pearson,
            "AmpCouplingCol": amp_coupling_col,
            "AmpCouplingLag": amp_coupling_lag,
            "AmpCouplingPearson": amp_coupling_pearson,
            "A_t": merged["A_t"],
            "C_t": merged["C_t"],
            "E_t": merged["E_t"],
            "H_t": merged["H_t"],
            "phi_h": merged["phi_h"],
            "phi_e": merged["phi_e"],
            "HSTResDrift": hst_res_drift,
            "HSTAmpCorr": hst_amp_corr,
            "HSTTempCorr": hst_temp_corr,
            "HSTPhaseDiv": hst_phase_div,
            "MoonAge": moon_age,
            "Amplitude": amplitude,
            "EventIntensity": event_intensity,
            "MemoryCharge": memory_charge,
            "Afterglow": afterglow,
            "MemoryPhase": memory_phase,
            "MemoryDrift": memory_drift,
            "MemoryPhaseCoherence": memory_phase_coh,
            "GhostLevel": ghost_level,
            "GhostStabilityIndex": ghost_stability,
            "WVI": wvi,
            "EnvPressure": env_pressure,
            "EnvFactor": env_factor,
        }
    )

    # Sort and compute dynamics
    journal = journal.sort_values("Date").reset_index(drop=True)
    journal = _compute_dynamics(journal)

    # Canonical column order
    canonical_order = [
        "Date",
        "Season",
        "SignalState",
        "ResonanceValue",
        "PrevState",
        "ChangeType",
        "StreakLength",
        "Phase",
        "SP500Close",
        "VIXClose",
        "TempAvg",
        "MoonIllum",
        "CouplingCol",
        "CouplingLag",
        "CouplingPearson",
        "AmpCouplingCol",
        "AmpCouplingLag",
        "AmpCouplingPearson",
        "A_t",
        "C_t",
        "E_t",
        "H_t",
        "phi_h",
        "phi_e",
        "HSTResDrift",
        "HSTAmpCorr",
        "HSTTempCorr",
        "HSTPhaseDiv",
        "MoonAge",
        "Amplitude",
        "EventIntensity",
        "MemoryCharge",
        "Afterglow",
        "MemoryPhase",
        "MemoryDrift",
        "MemoryPhaseCoherence",
        "GhostLevel",
        "GhostStabilityIndex",
        "WVI",
        "EnvPressure",
        "EnvFactor",
    ]

    journal = journal[canonical_order]

    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    journal.to_csv(JOURNAL_PATH, index=False)

    print("✅ Journal v3 rebuilt successfully.")
    print(f"   → Rows: {len(journal)}")
    print(f"   → Saved: {JOURNAL_PATH}")


if __name__ == "__main__":
    rebuild_journal()
