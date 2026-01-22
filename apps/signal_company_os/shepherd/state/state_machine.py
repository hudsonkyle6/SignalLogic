# rhythm_os/core/state_machine.py
"""
PROMOTED MODULE — Jan 2026

Originally part of Rhythm OS Core.
Relocated when Core was sealed as a
pure observational kernel.

This module performs interpretive
state evaluation and therefore belongs
to Shepherd-level governance.
"""

"""
Rhythm OS — StateMachine (PURE) — V1.1

Purpose:
  Compute "memory" fields deterministically from an in-memory history table.

This module MUST NOT:
  - read files
  - write files
  - mutate journal or merged

It returns a dict of memory fields to be applied by callers.

Memory fields (canonical):
  PrevState
  ChangeType   -> "New" | "Continue" | "Shift"
  StreakLength -> int (>=1), counts consecutive days INCLUDING today
  Phase        -> "Emerging" | "Consolidating" | "Persisting" | "Break"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd


# ----------------------------
# Datatypes
# ----------------------------

@dataclass(frozen=True)
class TodaySnapshot:
    date: pd.Timestamp
    season: str
    state: str
    resonance: float = 0.0
    sp_close: Optional[float] = None
    vix_close: Optional[float] = None
    temp_avg: Optional[float] = None
    moon_illum: Optional[float] = None

    # Coupling
    coupling_col: Optional[str] = None
    coupling_lag: Optional[int] = None
    coupling_pearson: Optional[float] = None
    amp_coupling_col: Optional[str] = None
    amp_coupling_lag: Optional[int] = None
    amp_coupling_pearson: Optional[float] = None

    # HST (optional passthrough)
    a_t: Optional[float] = None
    c_t: Optional[float] = None
    e_t: Optional[float] = None
    h_t: Optional[float] = None
    phi_h: Optional[float] = None
    phi_e: Optional[float] = None
    hst_res_drift: Optional[float] = None
    hst_amp_corr: Optional[float] = None
    hst_temp_corr: Optional[float] = None
    hst_phase_div: Optional[float] = None


# ----------------------------
# Pure StateMachine
# ----------------------------

class StateMachine:
    """
    Pure evaluator.

    Call:
      evaluate(today_snapshot, history_df=df)

    history_df requirements:
      - must include a Date column (any parseable format)
      - must include a state column: SignalState or State
    """

    def __init__(self, *, date_col: str = "Date"):
        self.date_col = date_col

    def evaluate(self, today: TodaySnapshot, history_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        today_date = pd.to_datetime(today.date, errors="coerce")
        if pd.isna(today_date):
            raise ValueError("TodaySnapshot.date is not parseable")

        today_state = self._norm_state(today.state)
        if today_state is None:
            # If caller gave a bad state, we cannot compute meaningfully.
            return self._first_day()

        # No history => first day
        if history_df is None or history_df.empty:
            return self._first_day()

        df = history_df.copy()

        # Must have Date
        if self.date_col not in df.columns:
            return self._first_day()

        # Parse dates + drop invalid
        df[self.date_col] = pd.to_datetime(df[self.date_col], errors="coerce")
        df = df.dropna(subset=[self.date_col])

        # Pick state column
        state_col = self._pick_state_col(df)
        if state_col is None:
            return self._first_day()

        # Normalize state values
        df[state_col] = df[state_col].apply(self._norm_state)

        # Drop rows with null/invalid states
        df = df.dropna(subset=[state_col])

        # --- CRITICAL: enforce one-row-per-date invariant in-memory ---
        # If duplicates exist for a date, we keep the LAST one (most recent enrichment pass).
        df = df.sort_values(self.date_col).drop_duplicates(subset=[self.date_col], keep="last").reset_index(drop=True)

        # Previous history strictly before today
        prev_df = df[df[self.date_col] < today_date]
        if prev_df.empty:
            return self._first_day()

        prev_state = str(prev_df.iloc[-1][state_col])

        if prev_state == today_state:
            change = "Continue"
            streak = self._compute_streak(prev_df[state_col].tolist(), today_state)
        else:
            change = "Shift"
            streak = 1

        phase = self._phase(change_type=change, today_state=today_state, streak=streak)

        return {
            "PrevState": prev_state,
            "ChangeType": change,
            "StreakLength": int(streak),
            "Phase": phase,
        }

    # ----------------------------
    # Internals
    # ----------------------------

    def _pick_state_col(self, df: pd.DataFrame) -> Optional[str]:
        for c in ("SignalState", "State"):
            if c in df.columns:
                return c
        return None

    def _norm_state(self, s) -> Optional[str]:
        if s is None:
            return None
        try:
            s = str(s).strip()
        except Exception:
            return None
        if s == "" or s.lower() in ("nan", "none", "null"):
            return None
        return s

    def _compute_streak(self, past_states: list, today_state: str) -> int:
        """
        Count consecutive same-state days ending at yesterday + include today.
        Assumes past_states are already normalized strings and ordered by Date.
        """
        target = str(today_state)
        streak = 1  # include today
        for s in reversed(past_states):
            if str(s) == target:
                streak += 1
            else:
                break
        return streak

    def _phase(self, *, change_type: str, today_state: str, streak: int) -> str:
        """
        Deterministic, minimal, stable phase mapping.

        - New / Shift => Emerging
        - Continue + short streak => Emerging
        - Continue + longer streak => Consolidating (for calm regimes) or Persisting (for turbulent)
        - Optional: if state changes after long streak, caller will see Shift + Emerging (break implied)
        """
        s = today_state.lower()

        if change_type == "New":
            return "Emerging"
        if change_type == "Shift":
            return "Emerging"

        # Continue
        if streak <= 2:
            return "Emerging"

        if ("turb" in s) or ("storm" in s):
            return "Persisting"

        # default (Still / Resonant / etc.)
        return "Consolidating"

    def _first_day(self) -> Dict[str, Any]:
        return {
            "PrevState": None,
            "ChangeType": "New",
            "StreakLength": 1,
            "Phase": "Emerging",
        }
