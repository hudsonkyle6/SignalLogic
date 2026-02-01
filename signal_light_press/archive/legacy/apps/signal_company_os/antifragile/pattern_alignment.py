import sys
from pathlib import Path

import pandas as pd
from ...kernel.wave import Wave  # three dots for one level up
from ...kernel.codex import Codex

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
JOURNAL_PATH = DATA_DIR / "journal" / "signal_journal.csv"
HUMAN_DIR = DATA_DIR / "human"
HUMAN_LEDGER_PATH = HUMAN_DIR / "human_ledger.csv"
TIDE_PATH = HUMAN_DIR / "tide_index.csv"
PATTERN_PATH = HUMAN_DIR / "pattern_alignment.csv"


def ensure_human_dirs():
    HUMAN_DIR.mkdir(parents=True, exist_ok=True)


def build_pattern_alignment():
    """
    Merge:
      - signal_journal.csv (world)
      - human_ledger.csv   (human)
      - tide_index.csv     (environment/tide)

    into a single pattern_alignment.csv keyed by Date.

    This is the core dataset for Antifragile + Lighthouse training.
    """
    ensure_human_dirs()

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"signal_journal.csv not found at {JOURNAL_PATH}."
        )
    if not HUMAN_LEDGER_PATH.exists():
        raise FileNotFoundError(
            f"human_ledger.csv not found at {HUMAN_LEDGER_PATH}."
        )
    if not TIDE_PATH.exists():
        raise FileNotFoundError(
            f"tide_index.csv not found at {TIDE_PATH}. Run the Tide Engine."
        )

    journal = pd.read_csv(JOURNAL_PATH)
    human = pd.read_csv(HUMAN_LEDGER_PATH)
    tide = pd.read_csv(TIDE_PATH)

    # normalize dates
    for df in (journal, human, tide):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)

    journal = journal.sort_values("Date")
    human = human.sort_values("Date")
    tide = tide.sort_values("Date")

    # drop heavy or text columns you don't want the model to ingest directly
    # (we keep Notes for human review but not in the ML-ready alignment;
    #  this is a human–machine boundary)
    human_for_merge = human.drop(columns=["Notes"], errors="ignore")

    # world + human
    merged = pd.merge(
        journal,
        human_for_merge,
        on="Date",
        how="inner",
        suffixes=("", "_human"),
    )

    # add tide
    tide_cols = [
        "Date",
        "TempAnomaly",
        "TempComponent",
        "MoonPressure",
        "MarketPressure",
        "SeasonalLoadIndex",
        "EnvPressureIndex",
        "EnergyWindow",
    ]
    tide_for_merge = tide[tide_cols]

    merged = pd.merge(
        merged,
        tide_for_merge,
        on="Date",
        how="left",
        suffixes=("", "_tide"),
    )

    # final clean-up
    merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")

    merged.to_csv(PATTERN_PATH, index=False)

    print(f"📘 Pattern Alignment DB written → {PATTERN_PATH}")
    print(f"   Rows: {len(merged)}")
    if not merged.empty:
        latest = merged.iloc[-1]
        print("══════════════════════════════════════")
        print("  🔗 PATTERN ALIGNMENT — LAST ENTRY")
        print("══════════════════════════════════════")
        print(f" Date:          {latest['Date']}")
        print(f" SignalState:   {latest.get('SignalState', '')}")
        print(f" DecisionState: {latest.get('DecisionState', '')}")
        print(f" CompassState:  {latest.get('CompassState', '')}")
        print("══════════════════════════════════════")


if __name__ == "__main__":
    try:
        build_pattern_alignment()
    except Exception as e:
        print("❌ Error:", e)
        sys.exit(1)
