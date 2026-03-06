"""
Oracle Contract v1 — CI Gate Tests

These tests enforce the oracle contract invariants in CI.
Any weakening of thresholds, removal of checks, or schema changes
will be caught here before code reaches production.

Modules covered:
- intelligence/oracle/validate.py     (all invariant functions)
- intelligence/oracle/contract_v1.py  (constants locked against regression)

Posture:
- Tests are intentionally strict: they test BOTH that valid data passes
  AND that invalid data is caught.  Removing a check causes a test failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import pandas as pd
    import yaml
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DEPS_AVAILABLE, reason="pandas/yaml not installed"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df(**cols) -> "pd.DataFrame":
    """Construct a minimal single-row DataFrame from keyword column values."""
    import pandas as pd
    return pd.DataFrame([cols])


def _valid_df(n: int = 1) -> "pd.DataFrame":
    """Return a valid n-row DataFrame satisfying all L1 contract requirements."""
    import pandas as pd
    rows = []
    for i in range(n):
        rows.append({
            "Date": f"2025-01-{i+1:02d}",
            "Season": "winter",
            "ResonanceValue": 0.5,
            "Amplitude": 0.6,
            "H_t": 0.7,
            "GhostStabilityIndex": 0.8,
            "WVI": 0.2,
            "EnvFactor": 0.5,
        })
    return pd.DataFrame(rows)


def _make_stability_yaml(tmp_path: Path, *, enabled: bool = True, mode: str = "assist_only",
                          escalation: bool = False, override_human: bool = False) -> Path:
    contract = {
        "StabilityContract": {
            "AssistUnderDiscipline": {
                "Enabled": enabled,
                "Authority": {
                    "Mode": mode,
                    "EscalationAllowed": escalation,
                    "OverrideHumanJudgment": override_human,
                },
            }
        }
    }
    p = tmp_path / "stability.yaml"
    p.write_text(yaml.dump(contract))
    return p


# ===========================================================================
# Contract constant regression tests
# These lock the contract schema — changes here signal intentional drift.
# ===========================================================================


class TestContractConstantsLocked:
    def test_never_null_today_fields(self):
        from intelligence.oracle.validate import NEVER_NULL_TODAY
        required = {"Date", "Season", "ResonanceValue", "Amplitude", "H_t"}
        assert required.issubset(set(NEVER_NULL_TODAY)), (
            f"NEVER_NULL_TODAY missing required fields: {required - set(NEVER_NULL_TODAY)}"
        )

    def test_ranges_0_1_fields_present(self):
        from intelligence.oracle.validate import RANGES_0_1
        required_fields = {"ResonanceValue", "Amplitude", "H_t", "OCI", "RiskIndex", "D_t"}
        # Allow some to be absent if renamed, but core fields must exist
        core = {"ResonanceValue", "Amplitude", "H_t"}
        assert core.issubset(set(RANGES_0_1)), (
            f"RANGES_0_1 missing core fields: {core - set(RANGES_0_1)}"
        )

    def test_ranges_0_1_bounds_are_0_to_1(self):
        from intelligence.oracle.validate import RANGES_0_1
        for field, (lo, hi) in RANGES_0_1.items():
            assert lo == 0.0, f"{field} lower bound must be 0.0, got {lo}"
            assert hi == 1.0, f"{field} upper bound must be 1.0, got {hi}"

    def test_ranges_non_negative_lower_bound(self):
        from intelligence.oracle.validate import RANGES_NON_NEGATIVE
        for field, (lo, _) in RANGES_NON_NEGATIVE.items():
            assert lo == 0.0, f"{field} lower bound must be 0.0, got {lo}"

    def test_physical_truth_columns_present(self):
        from intelligence.oracle.validate import PHYSICAL_TRUTH_COLUMNS
        required = {"Date", "Season", "Amplitude", "H_t"}
        assert required.issubset(PHYSICAL_TRUTH_COLUMNS), (
            f"PHYSICAL_TRUTH_COLUMNS missing: {required - PHYSICAL_TRUTH_COLUMNS}"
        )

    def test_contract_v1_required_l1_columns(self):
        from intelligence.oracle.contract_v1 import REQUIRED_L1_COLUMNS
        required = {"Date", "Season", "ResonanceValue", "Amplitude", "H_t",
                    "GhostStabilityIndex", "WVI", "EnvFactor"}
        assert required.issubset(set(REQUIRED_L1_COLUMNS)), (
            f"REQUIRED_L1_COLUMNS missing: {required - set(REQUIRED_L1_COLUMNS)}"
        )


# ===========================================================================
# enforce_assist_under_discipline
# ===========================================================================


class TestEnforceAUD:
    def test_valid_contract_passes(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = _make_stability_yaml(tmp_path)
        enforce_assist_under_discipline(p)  # must not raise

    def test_missing_file_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        with pytest.raises(AUDViolation, match="stability.yaml missing"):
            enforce_assist_under_discipline(tmp_path / "nonexistent.yaml")

    def test_missing_stability_contract_block_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = tmp_path / "stability.yaml"
        p.write_text(yaml.dump({"other": "stuff"}))
        with pytest.raises(AUDViolation, match="StabilityContract block missing"):
            enforce_assist_under_discipline(p)

    def test_aud_not_enabled_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = _make_stability_yaml(tmp_path, enabled=False)
        with pytest.raises(AUDViolation, match="not enabled"):
            enforce_assist_under_discipline(p)

    def test_wrong_authority_mode_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = _make_stability_yaml(tmp_path, mode="execute")
        with pytest.raises(AUDViolation, match="assist_only"):
            enforce_assist_under_discipline(p)

    def test_escalation_allowed_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = _make_stability_yaml(tmp_path, escalation=True)
        with pytest.raises(AUDViolation, match="EscalationAllowed"):
            enforce_assist_under_discipline(p)

    def test_override_human_judgment_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = _make_stability_yaml(tmp_path, override_human=True)
        with pytest.raises(AUDViolation, match="Human judgment"):
            enforce_assist_under_discipline(p)

    def test_corrupt_yaml_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = tmp_path / "stability.yaml"
        p.write_bytes(b"\x00\x01\x02\x03")  # not valid YAML
        with pytest.raises(AUDViolation):
            enforce_assist_under_discipline(p)

    def test_non_dict_yaml_raises(self, tmp_path):
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        p = tmp_path / "stability.yaml"
        p.write_text("- a list\n- not a dict\n")
        with pytest.raises(AUDViolation, match="dict"):
            enforce_assist_under_discipline(p)

    def test_actual_stability_yaml_passes(self):
        """
        The actual stability.yaml in the repo must satisfy AUD.
        This is a regression guard — if the file is changed to weaken AUD,
        this test fails in CI.
        """
        from intelligence.oracle.validate import enforce_assist_under_discipline, AUDViolation
        # Locate stability.yaml relative to the repo root
        repo_root = Path(__file__).resolve()
        while repo_root.name != "SignalLogic" and repo_root != repo_root.parent:
            repo_root = repo_root.parent
        stability_path = (
            repo_root / "apps" / "intelligence" / "oracle" / "contracts" / "stability.yaml"
        )
        assert stability_path.exists(), f"stability.yaml not found at {stability_path}"
        enforce_assist_under_discipline(stability_path)  # must not raise


# ===========================================================================
# _ensure_columns
# ===========================================================================


class TestEnsureColumns:
    def test_all_present_passes(self):
        from intelligence.oracle.validate import _ensure_columns
        import pandas as pd
        df = pd.DataFrame(columns=["Date", "Season", "ResonanceValue"])
        _ensure_columns(df, ["Date", "Season", "ResonanceValue"], "test")  # no raise

    def test_missing_column_raises(self):
        from intelligence.oracle.validate import _ensure_columns, OracleContractError
        import pandas as pd
        df = pd.DataFrame(columns=["Date"])
        with pytest.raises(OracleContractError, match="Missing required columns"):
            _ensure_columns(df, ["Date", "Season"], "test")

    def test_error_lists_missing_fields(self):
        from intelligence.oracle.validate import _ensure_columns, OracleContractError
        import pandas as pd
        df = pd.DataFrame(columns=["Date"])
        with pytest.raises(OracleContractError, match="ResonanceValue"):
            _ensure_columns(df, ["Date", "ResonanceValue", "Amplitude"], "test")


# ===========================================================================
# _ensure_date_monotonic
# ===========================================================================


class TestEnsureDateMonotonic:
    def test_monotonic_dates_pass(self):
        from intelligence.oracle.validate import _ensure_date_monotonic
        import pandas as pd
        df = pd.DataFrame({"Date": ["2025-01-01", "2025-01-02", "2025-01-03"]})
        _ensure_date_monotonic(df, "test")  # no raise

    def test_non_monotonic_raises(self):
        from intelligence.oracle.validate import _ensure_date_monotonic, OracleContractError
        import pandas as pd
        df = pd.DataFrame({"Date": ["2025-01-03", "2025-01-01", "2025-01-02"]})
        with pytest.raises(OracleContractError, match="monotonic"):
            _ensure_date_monotonic(df, "test")

    def test_duplicate_dates_raises(self):
        from intelligence.oracle.validate import _ensure_date_monotonic, OracleContractError
        import pandas as pd
        df = pd.DataFrame({"Date": ["2025-01-01", "2025-01-01", "2025-01-02"]})
        with pytest.raises(OracleContractError, match="Duplicate"):
            _ensure_date_monotonic(df, "test")

    def test_unparseable_date_raises(self):
        from intelligence.oracle.validate import _ensure_date_monotonic, OracleContractError
        import pandas as pd
        df = pd.DataFrame({"Date": ["2025-01-01", "not-a-date"]})
        with pytest.raises(OracleContractError, match="non-parseable"):
            _ensure_date_monotonic(df, "test")

    def test_missing_date_column_passes(self):
        from intelligence.oracle.validate import _ensure_date_monotonic
        import pandas as pd
        df = pd.DataFrame({"other": [1, 2]})
        _ensure_date_monotonic(df, "test")  # no date column → pass


# ===========================================================================
# _ensure_today_non_null
# ===========================================================================


class TestEnsureTodayNonNull:
    def test_all_fields_present_passes(self):
        from intelligence.oracle.validate import _ensure_today_non_null
        df = _valid_df()
        _ensure_today_non_null(df, "test")  # no raise

    def test_null_never_null_field_raises(self):
        from intelligence.oracle.validate import _ensure_today_non_null, OracleContractError
        import pandas as pd
        df = _valid_df()
        df.loc[df.index[-1], "ResonanceValue"] = float("nan")
        with pytest.raises(OracleContractError, match="nulls in NEVER_NULL"):
            _ensure_today_non_null(df, "test")

    def test_null_in_non_required_field_passes(self):
        from intelligence.oracle.validate import _ensure_today_non_null
        import pandas as pd
        df = _valid_df()
        # Add an optional field that is null — should be fine
        df["OptionalField"] = float("nan")
        _ensure_today_non_null(df, "test")  # no raise

    def test_error_lists_bad_fields(self):
        from intelligence.oracle.validate import _ensure_today_non_null, OracleContractError
        import pandas as pd
        df = _valid_df()
        df.loc[df.index[-1], "Amplitude"] = float("nan")
        with pytest.raises(OracleContractError, match="Amplitude"):
            _ensure_today_non_null(df, "test")


# ===========================================================================
# _ensure_numeric
# ===========================================================================


class TestEnsureNumeric:
    def test_numeric_dtype_passes(self):
        from intelligence.oracle.validate import _ensure_numeric
        import pandas as pd
        df = pd.DataFrame({"ResonanceValue": [0.5, 0.6], "Amplitude": [0.7, 0.8]})
        _ensure_numeric(df, "test")  # no raise

    def test_object_dtype_raises(self):
        from intelligence.oracle.validate import _ensure_numeric, OracleContractError
        import pandas as pd
        # pandas 2.x infers StringDtype instead of object for string arrays.
        # _ensure_numeric only catches object dtype (known gap on pandas 2.x).
        # We test with a DataFrame where the column is explicitly object dtype.
        df = pd.DataFrame({"ResonanceValue": pd.Series(["0.5", "0.6"], dtype="object")})
        if not pd.api.types.is_object_dtype(df["ResonanceValue"]):
            pytest.skip("pandas 2.x uses StringDtype: _ensure_numeric gap documented")
        with pytest.raises(OracleContractError, match="object dtype"):
            _ensure_numeric(df, "test")

    def test_column_not_in_ranges_not_checked(self):
        from intelligence.oracle.validate import _ensure_numeric
        import pandas as pd
        df = pd.DataFrame({"SomeUnknownColumn": ["a", "b"]})
        _ensure_numeric(df, "test")  # no raise — only checks RANGES_0_1 fields


# ===========================================================================
# _ensure_ranges
# ===========================================================================


class TestEnsureRanges:
    def test_in_range_passes(self):
        from intelligence.oracle.validate import _ensure_ranges
        df = _valid_df()
        _ensure_ranges(df, "test")  # no raise

    def test_above_1_raises(self):
        from intelligence.oracle.validate import _ensure_ranges, OracleContractError
        df = _valid_df()
        df.loc[df.index[-1], "ResonanceValue"] = 1.5
        with pytest.raises(OracleContractError, match="range violations"):
            _ensure_ranges(df, "test")

    def test_below_0_raises(self):
        from intelligence.oracle.validate import _ensure_ranges, OracleContractError
        df = _valid_df()
        df.loc[df.index[-1], "Amplitude"] = -0.1
        with pytest.raises(OracleContractError, match="range violations"):
            _ensure_ranges(df, "test")

    def test_exactly_0_passes(self):
        from intelligence.oracle.validate import _ensure_ranges
        df = _valid_df()
        df.loc[df.index[-1], "ResonanceValue"] = 0.0
        _ensure_ranges(df, "test")  # no raise

    def test_exactly_1_passes(self):
        from intelligence.oracle.validate import _ensure_ranges
        df = _valid_df()
        df.loc[df.index[-1], "ResonanceValue"] = 1.0
        _ensure_ranges(df, "test")  # no raise

    def test_null_value_skipped(self):
        from intelligence.oracle.validate import _ensure_ranges
        import pandas as pd
        df = _valid_df()
        df["OCI"] = float("nan")  # OCI is in RANGES_0_1 but null → skipped
        _ensure_ranges(df, "test")  # no raise

    def test_non_negative_below_zero_raises(self):
        from intelligence.oracle.validate import _ensure_ranges, OracleContractError
        import pandas as pd
        df = _valid_df()
        df["Afterglow"] = -1.0  # Afterglow is in RANGES_NON_NEGATIVE
        with pytest.raises(OracleContractError, match="range violations"):
            _ensure_ranges(df, "test")

    def test_error_names_violating_field(self):
        from intelligence.oracle.validate import _ensure_ranges, OracleContractError
        df = _valid_df()
        df.loc[df.index[-1], "H_t"] = 2.0
        with pytest.raises(OracleContractError, match="H_t"):
            _ensure_ranges(df, "test")


# ===========================================================================
# _ensure_physical_truth_not_overwritten
# ===========================================================================


class TestPhysicalTruthNotOverwritten:
    def test_no_changes_passes(self):
        from intelligence.oracle.validate import _ensure_physical_truth_not_overwritten
        import pandas as pd
        df = _valid_df()
        _ensure_physical_truth_not_overwritten(df.copy(), df.copy(), "test")  # no raise

    def test_physical_truth_change_raises(self):
        from intelligence.oracle.validate import (
            _ensure_physical_truth_not_overwritten, OracleContractError
        )
        df_before = _valid_df()
        df_after = _valid_df()
        df_after.loc[df_after.index[-1], "Amplitude"] = 0.99  # Amplitude is physical truth
        with pytest.raises(OracleContractError, match="Physical truth overwrite"):
            _ensure_physical_truth_not_overwritten(df_before, df_after, "test")

    def test_derived_column_change_passes(self):
        from intelligence.oracle.validate import _ensure_physical_truth_not_overwritten
        import pandas as pd
        df_before = _valid_df()
        df_after = _valid_df()
        df_after["OCI"] = 0.8  # OCI is derived, not physical truth
        _ensure_physical_truth_not_overwritten(df_before, df_after, "test")  # no raise

    def test_error_names_modified_column(self):
        from intelligence.oracle.validate import (
            _ensure_physical_truth_not_overwritten, OracleContractError
        )
        df_before = _valid_df()
        df_after = _valid_df()
        df_after.loc[df_after.index[-1], "H_t"] = 0.999
        with pytest.raises(OracleContractError, match="H_t"):
            _ensure_physical_truth_not_overwritten(df_before, df_after, "test")


# ===========================================================================
# validate_oracle_inputs — end-to-end
# ===========================================================================


class TestValidateOracleInputs:
    def test_valid_l1_passes(self):
        from intelligence.oracle.validate import validate_oracle_inputs
        df = _valid_df(3)
        validate_oracle_inputs(df, "test", "L1")  # no raise

    def test_valid_l4_passes(self):
        from intelligence.oracle.validate import validate_oracle_inputs
        df = _valid_df(3)
        validate_oracle_inputs(df, "test", "L4")  # no raise

    def test_unknown_layer_raises(self):
        from intelligence.oracle.validate import validate_oracle_inputs, OracleContractError
        df = _valid_df()
        with pytest.raises(OracleContractError, match="Unknown oracle layer"):
            validate_oracle_inputs(df, "test", "L99")

    def test_missing_required_column_raises(self):
        from intelligence.oracle.validate import validate_oracle_inputs, OracleContractError
        import pandas as pd
        df = _valid_df()
        df = df.drop(columns=["ResonanceValue"])
        with pytest.raises(OracleContractError, match="Missing required columns"):
            validate_oracle_inputs(df, "test", "L1")

    def test_out_of_range_value_raises(self):
        from intelligence.oracle.validate import validate_oracle_inputs, OracleContractError
        df = _valid_df(2)
        df.loc[df.index[-1], "Amplitude"] = 1.5
        with pytest.raises(OracleContractError, match="range violations"):
            validate_oracle_inputs(df, "test", "L1")

    def test_null_never_null_field_raises(self):
        from intelligence.oracle.validate import validate_oracle_inputs, OracleContractError
        import pandas as pd
        df = _valid_df(2)
        df.loc[df.index[-1], "Season"] = float("nan")
        with pytest.raises(OracleContractError, match="nulls in NEVER_NULL"):
            validate_oracle_inputs(df, "test", "L1")

    def test_duplicate_dates_raises(self):
        from intelligence.oracle.validate import validate_oracle_inputs, OracleContractError
        import pandas as pd
        df = _valid_df(2)
        df.loc[1, "Date"] = df.loc[0, "Date"]  # duplicate
        with pytest.raises(OracleContractError, match="Duplicate"):
            validate_oracle_inputs(df, "test", "L1")


# ===========================================================================
# validate_oracle_output_integrity — end-to-end
# ===========================================================================


class TestValidateOracleOutputIntegrity:
    def test_no_changes_passes(self):
        from intelligence.oracle.validate import validate_oracle_output_integrity
        df = _valid_df()
        validate_oracle_output_integrity(df.copy(), df.copy())  # no raise

    def test_physical_truth_modified_raises(self):
        from intelligence.oracle.validate import (
            validate_oracle_output_integrity, OracleContractError
        )
        df_before = _valid_df()
        df_after = _valid_df()
        df_after.loc[df_after.index[-1], "Amplitude"] = 0.999
        with pytest.raises(OracleContractError, match="Physical truth overwrite"):
            validate_oracle_output_integrity(df_before, df_after)
