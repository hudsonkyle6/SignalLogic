"""
ANTIFRAGILE ENGINE — HUMAN LEDGER
Canonical daily human signal entry

Rules (non-negotiable):
• One row per date
• Date sourced from signal_journal (never user-entered)
• Physics (Resonance / Amplitude) sourced from merged_signal
• Re-running replaces today’s entry (idempotent)
• Schema-stable, human-readable, ARI-safe
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

JOURNAL_PATH = DATA / "journal" / "signal_journal.csv"
MERGED_PATH = DATA / "merged" / "merged_signal.csv"

HUMAN_DIR = DATA / "human"
LEDGER_PATH = HUMAN_DIR / "human_ledger.csv"

DECISION_STATES = ["WAIT", "PREPARE", "ACT", "PUSH"]


# --------------------------------------------------
# INIT
# --------------------------------------------------


def ensure_dirs():
    HUMAN_DIR.mkdir(parents=True, exist_ok=True)


def init_ledger_if_missing():
    if LEDGER_PATH.exists():
        return

    cols = [
        "Date",
        "Season",
        "SignalState",
        "ResonanceValue",
        "Amplitude",
        "BodyLoad",
        "Clarity",
        "Resistance",
        "StressLevel",
        "SleepQuality",
        "EnvFeel",
        "DecisionState",
        "Notes",
    ]

    pd.DataFrame(columns=cols).to_csv(LEDGER_PATH, index=False)
    print(f"📘 Initialized human ledger → {LEDGER_PATH}")


# --------------------------------------------------
# LOADERS
# --------------------------------------------------


def load_today_from_journal():
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            "signal_journal.csv not found. Run daily pipeline first."
        )

    df = pd.read_csv(JOURNAL_PATH, low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    if df.empty:
        raise ValueError("signal_journal.csv has no valid rows.")

    row = df.iloc[-1]

    return {
        "Date": row["Date"].strftime("%Y-%m-%d"),
        "Season": row.get("Season", ""),
        "SignalState": row.get("SignalState", ""),
    }


def load_physics_from_merged(date_str: str):
    if not MERGED_PATH.exists():
        return {"ResonanceValue": float("nan"), "Amplitude": float("nan")}

    df = pd.read_csv(MERGED_PATH, low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    row = df[df["Date"] == date_str]
    if row.empty:
        return {"ResonanceValue": float("nan"), "Amplitude": float("nan")}

    r = row.iloc[-1]
    return {
        "ResonanceValue": r.get("ResonanceValue", float("nan")),
        "Amplitude": r.get("Amplitude", float("nan")),
    }


# --------------------------------------------------
# PROMPTS
# --------------------------------------------------


def prompt_int(label: str):
    while True:
        val = input(f"{label} (1–5, blank=0): ").strip()
        if val == "":
            return 0
        try:
            n = int(val)
            if 1 <= n <= 5:
                return n
        except ValueError:
            pass
        print("Enter a number 1–5 or leave blank.")


def prompt_decision():
    print("\nDecision State:")
    for s in DECISION_STATES:
        print(" ", s)

    while True:
        val = input("Decision [WAIT/PREPARE/ACT/PUSH, blank=WAIT]: ").strip().upper()
        if val == "":
            return "WAIT"
        if val in DECISION_STATES:
            return val
        print("Invalid choice.")


# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------


def log_today_entry():
    ensure_dirs()
    init_ledger_if_missing()

    journal = load_today_from_journal()
    date = journal["Date"]

    physics = load_physics_from_merged(date)
    resonance = physics["ResonanceValue"]
    amplitude = physics["Amplitude"]

    print("══════════════════════════════════════")
    print("📘 ANTIFRAGILE ENGINE — HUMAN LEDGER")
    print("══════════════════════════════════════")
    print(f"Date:          {date}")
    print(f"Season:        {journal['Season']}")
    print(f"Signal State:  {journal['SignalState']}")
    print(
        f"Resonance:     {resonance:.3f}"
        if pd.notna(resonance)
        else "Resonance:     N/A"
    )
    print(
        f"Amplitude:     {amplitude:.3f}"
        if pd.notna(amplitude)
        else "Amplitude:     N/A"
    )
    print("──────────────────────────────────────")
    print("Enter human signals (1 = low, 5 = high)")
    print("──────────────────────────────────────")

    body = prompt_int("Body Load")
    clarity = prompt_int("Clarity")
    resist = prompt_int("Resistance")
    stress = prompt_int("Stress Level")
    sleep = prompt_int("Sleep Quality")
    env = prompt_int("Environmental Feel")

    notes = input("\nNotes (optional): ").strip()
    decision = prompt_decision()

    new_row = {
        "Date": date,
        "Season": journal["Season"],
        "SignalState": journal["SignalState"],
        "ResonanceValue": resonance,
        "Amplitude": amplitude,
        "BodyLoad": body,
        "Clarity": clarity,
        "Resistance": resist,
        "StressLevel": stress,
        "SleepQuality": sleep,
        "EnvFeel": env,
        "DecisionState": decision,
        "Notes": notes,
    }

    ledger = pd.read_csv(LEDGER_PATH, low_memory=False)
    ledger["Date"] = pd.to_datetime(ledger["Date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )

    # idempotent upsert
    ledger = ledger[ledger["Date"] != date].copy()

    for col in new_row:
        if col not in ledger.columns:
            ledger[col] = pd.NA

    ledger.loc[len(ledger)] = new_row
    ledger = ledger.sort_values("Date").reset_index(drop=True)

    ledger.to_csv(LEDGER_PATH, index=False)

    print("\n✅ Ledger updated →", LEDGER_PATH)
    print("══════════════════════════════════════")


if __name__ == "__main__":
    try:
        log_today_entry()
    except Exception as e:
        print("❌ Error:", e)
        sys.exit(1)
