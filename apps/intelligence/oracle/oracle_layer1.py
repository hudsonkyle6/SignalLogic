# rhythm_os/oracle/oracle_layer1.py
"""
Oracle OS — Layer 1: Harmonic Convergence Engine (OCI)

Authority Boundary:
- FIRST executable Oracle layer
- Enforces Assist Under Discipline (AUD) at runtime
- Assist-only, no escalation, no authority creep

Key canonical behavior:
- L1 MUST be telemetry-preserving.
- It computes OCI but also PASSES THROUGH structural observables already computed upstream
  (GhostShadow, GhostMemoryPressure, etc.) so oracle_state.csv does not lose fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import numpy as np
import pandas as pd
import yaml

from rhythm_os.oracle.validate import validate_oracle_inputs


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"
ORACLE_DIR = DATA_DIR / "oracle"
ORACLE_STATE_PATH = ORACLE_DIR / "oracle_state.csv"

STABILITY_CONTRACT_PATH = ROOT / "rhythm_os" / "oracle" / "contracts" / "stability.yaml"


# ---------------------------------------------------------------------
# AUD Guardrail — Assist Under Discipline
# ---------------------------------------------------------------------


def _require_aud_guardrail() -> None:
    """
    HARD GUARDRAIL:
    Oracle may not execute unless Assist Under Discipline
    is present, enabled, and authority-limited.
    """
    if not STABILITY_CONTRACT_PATH.exists():
        raise RuntimeError(
            f"AUD VIOLATION: stability.yaml missing → {STABILITY_CONTRACT_PATH}"
        )

    try:
        with open(STABILITY_CONTRACT_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(f"AUD VIOLATION: cannot read stability.yaml ({e})")

    if not isinstance(cfg, dict):
        raise RuntimeError("AUD VIOLATION: stability.yaml did not parse to a dict")

    contract = cfg.get("StabilityContract")
    if not isinstance(contract, dict):
        raise RuntimeError("AUD VIOLATION: StabilityContract missing or invalid")

    aud = contract.get("AssistUnderDiscipline")
    if not isinstance(aud, dict):
        raise RuntimeError(
            "AUD VIOLATION: AssistUnderDiscipline missing from StabilityContract"
        )

    if aud.get("Enabled") is not True:
        raise RuntimeError("AUD VIOLATION: AssistUnderDiscipline not enabled")

    authority = aud.get("Authority", {})
    if authority.get("Mode") != "assist_only":
        raise RuntimeError("AUD VIOLATION: Authority.Mode must be 'assist_only'")

    if authority.get("EscalationAllowed") is True:
        raise RuntimeError("AUD VIOLATION: EscalationAllowed must be false")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _sigmoid(x: float, k: float = 1.0) -> float:
    return 1.0 / (1.0 + np.exp(-k * float(x)))


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _passthrough(latest: pd.Series, key: str, default=pd.NA):
    """Telemetry-preserving passthrough from merged_signal into oracle_state."""
    try:
        if key in latest.index:
            v = latest.get(key, default)
            return default if pd.isna(v) else v
        return default
    except Exception:
        return default


# ---------------------------------------------------------------------
# Oracle Input Loader (CANONICAL)
# ---------------------------------------------------------------------


def _load_merged_for_oracle() -> pd.DataFrame:
    if not MERGED_PATH.exists():
        raise RuntimeError("merged_signal.csv missing")

    df = pd.read_csv(MERGED_PATH)

    # Canonical sanitation
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)

    # Validate merged input
    validate_oracle_inputs(df, ctx="ORACLE_L1_INPUT", layer="L1")
    return df


# ---------------------------------------------------------------------
# Upsert helper (no validation here)
# ---------------------------------------------------------------------


def _upsert_by_date(path: Path, row: Dict[str, Any], date_col: str = "Date") -> None:
    ORACLE_DIR.mkdir(parents=True, exist_ok=True)

    df = _read_csv_safe(path)
    d = row.get(date_col)
    if d is None:
        raise ValueError("Row missing Date")

    if df.empty:
        pd.DataFrame([row]).to_csv(path, index=False)
        return

    if date_col not in df.columns:
        df[date_col] = pd.NA

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

    # Add any missing columns (schema growth allowed)
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


# ---------------------------------------------------------------------
# Core Computation
# ---------------------------------------------------------------------


def compute_oracle_row(df: pd.DataFrame) -> Dict[str, Any]:
    latest = df.iloc[-1]
    window = df.tail(60)

    res_today = _safe_float(latest.get("ResonanceValue"))
    res_series = pd.to_numeric(
        window.get("ResonanceValue", pd.Series(dtype="float64")), errors="coerce"
    )

    if res_series.notna().sum() >= 10:
        z = (res_today - res_series.mean()) / max(res_series.std(ddof=0), 1e-6)
        res_score = _sigmoid(z, 0.7)
    else:
        res_score = 0.5

    # Inputs
    stab = _clip01(_safe_float(latest.get("GhostStabilityIndex"), 0.5))
    wvi = _clip01(_safe_float(latest.get("WVI"), 0.0))
    env_factor = _clip01(_safe_float(latest.get("EnvFactor"), 0.5))
    drift = abs(_safe_float(latest.get("HSTResDrift"), 0.0))

    env_score = _clip01(0.6 * (1 - wvi) + 0.4 * env_factor)
    phase_score = _clip01(1 / (1 + drift / 0.1))

    oci = _clip01(
        0.35 * res_score + 0.30 * stab + 0.20 * env_score + 0.15 * phase_score
    )

    band = (
        "CALM"
        if oci >= 0.7
        else "FOCUSED"
        if oci >= 0.55
        else "CHOPPY"
        if oci >= 0.4
        else "STORM"
    )
    bias = (
        "FAVORABLE"
        if oci >= 0.7
        else "NEUTRAL-POSITIVE"
        if oci >= 0.55
        else "CAUTION"
        if oci >= 0.4
        else "RED"
    )

    # Telemetry-preserving row
    return {
        "Date": latest["Date"],
        "Season": latest.get("Season", "Unknown"),
        "SignalState": latest.get("SignalState", latest.get("State", "N/A")),
        "ResonanceValue": res_today,
        "Amplitude": _safe_float(latest.get("Amplitude")),
        "H_t": _safe_float(latest.get("H_t")),
        "GhostStabilityIndex": stab,
        # ✅ PASS-THROUGH (precomputed upstream)
        "GhostShadow": _passthrough(latest, "GhostShadow", pd.NA),
        "GhostMemoryPressure": _passthrough(latest, "GhostMemoryPressure", pd.NA),
        "WVI": wvi,
        "EnvFactor": env_factor,
        "HSTResDrift": _safe_float(latest.get("HSTResDrift")),
        "OracleConvergenceIndex": oci,
        "OracleRiskIndex": _clip01(1 - oci),
        "OracleBand": band,
        "OracleBias": bias,
    }


# ---------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------


def run_oracle_layer1():
    try:
        _require_aud_guardrail()
        df = _load_merged_for_oracle()
        row = compute_oracle_row(df)
        _upsert_by_date(ORACLE_STATE_PATH, row)

    except Exception as e:
        print("[ORACLE L1] ERROR:", e)
        return

    print("🔮 ORACLE L1 OK →", row["Date"])


if __name__ == "__main__":
    run_oracle_layer1()
