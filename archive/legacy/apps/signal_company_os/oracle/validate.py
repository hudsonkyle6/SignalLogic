from __future__ import annotations

from typing import List
from pathlib import Path
import pandas as pd
import yaml

from .contract_v1 import REQUIRED_L1_COLUMNS, REQUIRED_L4_COLUMNS


# ============================================================
# Contract constants
# ============================================================

# Fields that must NEVER be null on the current (last) row if present
NEVER_NULL_TODAY = [
    "Date",
    "Season",
    "ResonanceValue",
    "Amplitude",
    "H_t",
]

# Normalized [0,1] fields
RANGES_0_1 = {
    "ResonanceValue": (0.0, 1.0),
    "Amplitude": (0.0, 1.0),
    "H_t": (0.0, 1.0),
    "GhostStabilityIndex": (0.0, 1.0),
    "WVI": (0.0, 1.0),
    "EnvFactor": (0.0, 1.0),
    "OCI": (0.0, 1.0),
    "RiskIndex": (0.0, 1.0),
    "HCFIndex": (0.0, 1.0),
    "HorizonIndex": (0.0, 1.0),
    "D_t": (0.0, 1.0),
}

# Non-negative but uncapped fields
RANGES_NON_NEGATIVE = {
    "Afterglow": (0.0, float("inf")),
    "MemoryCharge": (0.0, float("inf")),
}


# ============================================================
# Errors
# ============================================================

class OracleContractError(RuntimeError):
    """Raised when Oracle contract invariants are violated."""
    pass


class AUDViolation(RuntimeError):
    """Raised when Assist Under Discipline is violated."""
    pass


# ============================================================
# Assist Under Discipline (AUD) enforcement
# ============================================================

def enforce_assist_under_discipline(stability_contract_path: Path) -> None:
    """
    HARD GUARDRAIL:
    The system may assist, but never escalate, act, or override human authority.
    """

    if not stability_contract_path.exists():
        raise AUDViolation(
            f"AUD VIOLATION: stability.yaml missing → {stability_contract_path}"
        )

    try:
        with open(stability_contract_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        raise AUDViolation(f"AUD VIOLATION: cannot read stability.yaml ({e})")

    if not isinstance(cfg, dict):
        raise AUDViolation("AUD VIOLATION: stability.yaml did not parse to dict")

    contract = cfg.get("StabilityContract")
    if not contract:
        raise AUDViolation("AUD VIOLATION: StabilityContract block missing")

    aud = contract.get("AssistUnderDiscipline")
    if not aud or not aud.get("Enabled", False):
        raise AUDViolation("AUD VIOLATION: AssistUnderDiscipline not enabled")

    authority = aud.get("Authority", {})

    if authority.get("Mode") != "assist_only":
        raise AUDViolation("AUD VIOLATION: Authority mode is not assist_only")

    if authority.get("EscalationAllowed", True):
        raise AUDViolation("AUD VIOLATION: EscalationAllowed must be false")

    if authority.get("OverrideHumanJudgment", True):
        raise AUDViolation("AUD VIOLATION: Human judgment override not permitted")


# ============================================================
# Invariant checks
# ============================================================

def _ensure_columns(df: pd.DataFrame, cols: List[str], ctx: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise OracleContractError(f"[{ctx}] Missing required columns: {missing}")


def _ensure_date_monotonic(df: pd.DataFrame, ctx: str) -> None:
    if "Date" not in df.columns:
        return

    s = pd.to_datetime(df["Date"], errors="coerce")

    if s.isna().any():
        raise OracleContractError(f"[{ctx}] Date contains non-parseable values.")

    if s.duplicated().any():
        raise OracleContractError(f"[{ctx}] Duplicate Date rows detected.")

    if not s.is_monotonic_increasing:
        raise OracleContractError(f"[{ctx}] Date is not monotonic increasing.")


def _ensure_today_non_null(df: pd.DataFrame, ctx: str) -> None:
    today = df.iloc[-1]

    bad = []
    for c in NEVER_NULL_TODAY:
        if c in df.columns and pd.isna(today[c]):
            bad.append(c)

    if bad:
        raise OracleContractError(
            f"[{ctx}] Today row has nulls in NEVER_NULL fields: {bad}"
        )


def _ensure_numeric(df: pd.DataFrame, ctx: str) -> None:
    for c in RANGES_0_1.keys():
        if c in df.columns:
            if pd.api.types.is_object_dtype(df[c]):
                raise OracleContractError(
                    f"[{ctx}] Column {c} is object dtype (coercion risk)"
                )


def _ensure_ranges(df: pd.DataFrame, ctx: str) -> None:
    today = df.iloc[-1]
    violations = []

    for c, (lo, hi) in RANGES_0_1.items():
        if c in df.columns:
            v = today[c]
            if pd.isna(v):
                continue
            fv = float(v)
            if fv < lo - 1e-9 or fv > hi + 1e-9:
                violations.append((c, fv, f"outside [{lo},{hi}]"))

    for c, (lo, _) in RANGES_NON_NEGATIVE.items():
        if c in df.columns:
            v = today[c]
            if pd.isna(v):
                continue
            fv = float(v)
            if fv < lo - 1e-9:
                violations.append((c, fv, f"below {lo}"))

    if violations:
        raise OracleContractError(
            f"[{ctx}] Today row range violations: {violations}"
        )


# ============================================================
# Public validator
# ============================================================

def validate_oracle_inputs(
    df: pd.DataFrame,
    ctx: str,
    layer: str,
) -> None:
    """
    Validate merged_signal.csv against Oracle Contract v1
    for the specified Oracle layer.
    """

    if layer == "L1":
        required_cols = REQUIRED_L1_COLUMNS
    elif layer == "L4":
        required_cols = REQUIRED_L4_COLUMNS
    else:
        raise OracleContractError(f"[{ctx}] Unknown oracle layer: {layer}")

    _ensure_columns(df, required_cols, ctx)
    _ensure_date_monotonic(df, ctx)
    _ensure_today_non_null(df, ctx)
    _ensure_numeric(df, ctx)
    _ensure_ranges(df, ctx)
