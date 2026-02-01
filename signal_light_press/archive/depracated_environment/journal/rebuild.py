"""
Journal Engine — rebuild.py
Rebuilds signal_journal.csv fully from merged_signal.csv.
This establishes the clean, canonical history for the Rhythm OS Journal.
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
MERGED = DATA / "merged" / "merged_signal.csv"
JOURNAL = DATA / "journal" / "signal_journal.csv"

# ---------------------------------------------------------
# Helper: Phase naming
# ---------------------------------------------------------
def map_phase_from_res(res_value: float) -> str:
    """
    Phase logic used historically by Rhythm OS.
    Only used as fallback when journal doesn't exist.
    """
    if res_value >= 0.66:
        return "Emerging"
    if res_value >= 0.25:
        return "Consolidating"
    if res_value > -0.25:
        return "Oscillating"
    if res_value > -0.66:
        return "Decaying"
    return "Anomalous"

# ---------------------------------------------------------
# Helper: Determine PrevState, Change, Streak
# ---------------------------------------------------------
def compute_journal_dynamics(df: pd.DataFrame):
    prev_states = [""]  # first row has no previous state
    changes = ["New"]
    streaks = [1]

    for i in range(1, len(df)):
        prev = df.loc[i-1, "SignalState"]
        curr = df.loc[i, "SignalState"]

        prev_states.append(prev)

        # Change type
        if curr == prev:
            change = "Continue"
        else:
            # Directional difference
            change = "Rise" if curr == "Resonant" and prev != "Resonant" else (
                     "Fall" if curr == "Turbulent" and prev != "Turbulent" else "Flip"
            )
        changes.append(change)

        # Streak
        if curr == prev:
            streaks.append(streaks[-1] + 1)
        else:
            streaks.append(1)

    df["PrevState"] = prev_states
    df["ChangeType"] = changes
    df["StreakLength"] = streaks
    return df

# ---------------------------------------------------------
# Rebuild Journal
# ---------------------------------------------------------
def rebuild_journal():
    print("📘 Rebuilding Signal Journal from merged_signal.csv...")
    if not MERGED.exists():
        raise FileNotFoundError(f"Cannot find merged_signal.csv at {MERGED}")

    merged = pd.read_csv(MERGED)
    
    # Normalize column names
    merged.columns = [c.strip() for c in merged.columns]

    # Build base journal
    journal = pd.DataFrame({
        "Date": merged["Date"],
        "Season": merged["Season"],
        "SignalState": merged["SignalState"],
        "ResonanceValue": merged["ResonanceValue"],
        "Phase": merged["ResonanceValue"].apply(map_phase_from_res),

        # Market & natural pulled straight across
        "SP500Close": merged["SP500Close"],
        "VIXClose": merged["VIXClose"],
        "TempAvg": merged["TempAvg"],
        "MoonIllum": merged["MoonIllum"],

        # Coupling left blank (filled in next module)
        "CouplingCol": "",
        "CouplingLag": "",
        "CouplingPearson": "",
        "AmpCouplingCol": "",
        "AmpCouplingLag": "",
        "AmpCouplingPearson": "",

        # HST fields straight across
        "A_t": merged["A_t"],
        "C_t": merged["C_t"],
        "E_t": merged["E_t"],
        "H_t": merged["H_t"],
        "phi_h": merged["phi_h"],
        "phi_e": merged["phi_e"],

        # Drift metrics blank for now (computed next)
        "HSTResDrift": "",
        "HSTAmpCorr": "",
        "HSTTempCorr": "",
        "HSTPhaseDiv": "",
    })

    # Compute PrevState / ChangeType / StreakLength
    journal = compute_journal_dynamics(journal)

    # Reorder to final canonical order
    canonical_order = [
        "Date", "Season", "SignalState", "ResonanceValue",
        "PrevState", "ChangeType", "StreakLength", "Phase",
        "SP500Close", "VIXClose", "TempAvg", "MoonIllum",
        "CouplingCol", "CouplingLag", "CouplingPearson",
        "AmpCouplingCol", "AmpCouplingLag", "AmpCouplingPearson",
        "A_t", "C_t", "E_t", "H_t", "phi_h", "phi_e",
        "HSTResDrift", "HSTAmpCorr", "HSTTempCorr", "HSTPhaseDiv"
    ]
    journal = journal[canonical_order]

    # Save
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    journal.to_csv(JOURNAL, index=False)

    print("✅ Journal rebuilt successfully.")
    print(f"   → Rows: {len(journal)}")
    print(f"   → Saved: {JOURNAL}")

if __name__ == "__main__":
    rebuild_journal()
