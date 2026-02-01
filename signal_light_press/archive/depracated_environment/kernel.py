# rhythm_os/core/kernel.py
"""
Rhythm OS Kernel — V3.4 (Silent + Diagnostic-Safe + UTF-8 Subprocess Boundary)

Kernel responsibilities (ONLY):
  1) Refresh NATURAL rhythm
  2) Run preparation pipeline -> updates merged_signal.csv
  3) Load smoothed merged_signal.csv
  4) Compute coupling + HST analytics
  5) Compute memory fields via PURE StateMachine (in-memory)
  6) Write enriched daily snapshot to data/merged/daily_YYYY-MM-DD.csv

Kernel MUST:
  - Be silent on success (no print(), no banners, no human-facing output)
  - Raise exceptions on failure
  - Write diagnostics to file only
  - Force UTF-8 on all subprocess boundaries (Windows-safe)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, date
from typing import Optional

import os
import sys
import subprocess
import numpy as np
import pandas as pd

from rhythm_os.core.loader import load_smoothed_merged_signal
from rhythm_os.core.coupling.live_coupling import compute_live_coupling, LiveCouplingResult
from rhythm_os.core.coupling.coupling import CouplingStat
from rhythm_os.core.state_machine import StateMachine, TodaySnapshot


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]  # SignalLogic/
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "merged"
DIAG_DIR = DATA_DIR / "diagnostics"

PYTHON = sys.executable
TODAY: date = datetime.now().date()

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
DIAG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SUBPROCESS BOUNDARY (UTF-8 + silent + diagnostics)
# ============================================================

def _utf8_env() -> dict:
    """
    Force UTF-8 for any child Python process so Windows cp1252 cannot crash
    on emoji/unicode/warnings produced by dependencies.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    # Optional hardening: uncomment if you want warnings suppressed globally in children.
    # env["PYTHONWARNINGS"] = "ignore"
    return env


def _run_module(
    module: str,
    *,
    must_succeed: bool,
    stderr_log: Optional[Path] = None,
) -> None:
    """
    Run `python -m <module>` with:
      - stdout discarded (silence)
      - stderr captured to a UTF-8 log file (if provided), otherwise discarded
      - UTF-8 enforced via env
    """
    if stderr_log is None:
        subprocess.run(
            [PYTHON, "-m", module],
            check=must_succeed,
            cwd=str(ROOT),
            env=_utf8_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    with stderr_log.open("w", encoding="utf-8") as err:
        subprocess.run(
            [PYTHON, "-m", module],
            check=must_succeed,
            cwd=str(ROOT),
            env=_utf8_env(),
            stdout=subprocess.DEVNULL,
            stderr=err,
        )


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _safe_float(row: pd.Series, key: str) -> Optional[float]:
    val = row.get(key)
    try:
        return float(val) if pd.notna(val) else None
    except Exception:
        return None


def _rolling_corr(series_a, series_b, window: int = 7, min_periods: int = 3) -> Optional[float]:
    s1 = pd.to_numeric(series_a, errors="coerce")
    s2 = pd.to_numeric(series_b, errors="coerce")
    tmp = pd.DataFrame({"a": s1, "b": s2}).dropna()
    if len(tmp) < min_periods:
        return None
    corr = tmp["a"].rolling(window, min_periods=min_periods).corr(tmp["b"])
    return float(corr.iloc[-1]) if not corr.dropna().empty else None


def _phase_divergence(phi_h, phi_e) -> Optional[float]:
    if phi_h is None or phi_e is None:
        return None
    diff = abs(float(phi_h) - float(phi_e))
    two_pi = 2.0 * np.pi
    while diff > two_pi:
        diff = abs(diff - two_pi)
    return float(two_pi - diff if diff > np.pi else diff)


def _hst_resonance_drift(h_t, resonance) -> Optional[float]:
    if h_t is None or resonance is None:
        return None
    h = float(h_t)
    r = float(resonance)
    h_norm = h / (1.0 + h) if h >= 0 else 0.0
    r_norm = (r + 1.0) / 2.0
    return float(h_norm - r_norm)


# ============================================================
# MAIN KERNEL
# ============================================================

def run_daily_kernel() -> Path:
    """
    Returns:
        Path to the written daily snapshot: data/merged/daily_YYYY-MM-DD.csv
    Raises:
        Any exception / CalledProcessError on failure.
    """

    # --------------------------------------------------------
    # 1) Refresh natural rhythm (best-effort)
    # --------------------------------------------------------
    _run_module(
        "rhythm_os.core.sources.load_natural",
        must_succeed=False,
        stderr_log=None,  # discard
    )

    # --------------------------------------------------------
    # 2) Preparation pipeline (must succeed; diagnostics to file)
    # --------------------------------------------------------
    prep_diag = DIAG_DIR / "prepare_daily_signals.stderr.log"
    _run_module(
        "rhythm_os.core.prepare_daily_signals",
        must_succeed=True,
        stderr_log=prep_diag,
    )

    # --------------------------------------------------------
    # 3) Load smoothed merged signal
    # --------------------------------------------------------
    df = load_smoothed_merged_signal()
    if df is None or df.empty:
        raise RuntimeError("Smoothed merged_signal is empty.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    last_ts = df["Date"].iloc[-1]
    today_row = df[df["Date"] == last_ts].iloc[-1].copy()

    # --------------------------------------------------------
    # 4) Coupling
    # --------------------------------------------------------
    best_coup: Optional[CouplingStat] = None
    best_amp_coup = None
    try:
        live: LiveCouplingResult = compute_live_coupling(df)
        best_coup = live.resonance
        best_amp_coup = live.amplitude
    except Exception:
        # lawful: coupling is best-effort; snapshot still writes
        pass

    # --------------------------------------------------------
    # 5) HST analytics
    # --------------------------------------------------------
    a_t = _safe_float(today_row, "A_t")
    c_t = _safe_float(today_row, "C_t")
    e_t = _safe_float(today_row, "E_t")
    h_t = _safe_float(today_row, "H_t")
    phi_h = _safe_float(today_row, "phi_h")
    phi_e = _safe_float(today_row, "phi_e")

    try:
        resonance_val = float(today_row.get("ResonanceValue", 0.0))
        if pd.isna(resonance_val):
            resonance_val = 0.0
    except Exception:
        resonance_val = 0.0

    df_window = df.tail(7)

    hst_amp_corr = _rolling_corr(df_window["H_t"], df_window["Amplitude"]) if "Amplitude" in df_window else None
    hst_temp_corr = _rolling_corr(df_window["A_t"], df_window["TempAvg"]) if "TempAvg" in df_window else None
    hst_phase_div = _phase_divergence(phi_h, phi_e)
    hst_res_drift = _hst_resonance_drift(h_t, resonance_val)

    # --------------------------------------------------------
    # 6) State machine (pure)
    # --------------------------------------------------------
    snapshot = TodaySnapshot(
        date=last_ts,
        season=str(today_row.get("Season", "Unknown")),
        state=str(today_row.get("SignalState", today_row.get("State", "Unknown"))),
        resonance=resonance_val,
        sp_close=_safe_float(today_row, "SP500Close"),
        vix_close=_safe_float(today_row, "VIXClose"),
        temp_avg=_safe_float(today_row, "TempAvg"),
        moon_illum=_safe_float(today_row, "MoonIllum"),
        coupling_col=getattr(best_coup, "col", None),
        coupling_lag=getattr(best_coup, "lag_days", None),
        coupling_pearson=getattr(best_coup, "pearson", None),
        amp_coupling_col=getattr(best_amp_coup, "col", None),
        amp_coupling_lag=getattr(best_amp_coup, "lag_days", None),
        amp_coupling_pearson=getattr(best_amp_coup, "pearson", None),
        a_t=a_t,
        c_t=c_t,
        e_t=e_t,
        h_t=h_t,
        phi_h=phi_h,
        phi_e=phi_e,
        hst_res_drift=hst_res_drift,
        hst_amp_corr=hst_amp_corr,
        hst_temp_corr=hst_temp_corr,
        hst_phase_div=hst_phase_div,
    )

    sm = StateMachine(date_col="Date")
    memory = sm.evaluate(snapshot, history_df=df)

    # --------------------------------------------------------
    # 7) Enrich + write snapshot
    # --------------------------------------------------------
    today_row["PrevState"] = memory.get("PrevState")
    today_row["ChangeType"] = memory.get("ChangeType")
    today_row["StreakLength"] = memory.get("StreakLength")
    today_row["Phase"] = memory.get("Phase")

    today_row["HSTResDrift"] = hst_res_drift
    today_row["HSTAmpCorr"] = hst_amp_corr
    today_row["HSTTempCorr"] = hst_temp_corr
    today_row["HSTPhaseDiv"] = hst_phase_div

    date_str = last_ts.strftime("%Y-%m-%d")
    out_path = SNAPSHOT_DIR / f"daily_{date_str}.csv"
    pd.DataFrame([today_row]).to_csv(out_path, index=False)

    return out_path



