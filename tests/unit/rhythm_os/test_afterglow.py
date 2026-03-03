"""
Tests for rhythm_os.core.memory.afterglow

Modules covered:
- _safe_col      (safe column accessor with default)
- _normalize     (0-1 normalization)
- compute_memory_fields  (hybrid event field computation)

Invariants:
- _safe_col returns a constant series for missing columns
- _normalize handles constant series without division by zero
- compute_memory_fields is safe on empty DataFrames
- EventIntensity, MemoryCharge, Afterglow, MemoryPhase columns are produced
- MemoryPhase labels are one of QUIET, ACTIVE, DECAY
"""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from rhythm_os.core.memory.afterglow import _safe_col, _normalize, compute_memory_fields  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_df(n: int = 20) -> "pd.DataFrame":
    """Minimal DataFrame that compute_memory_fields can process."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Date": dates,
            "ResonanceValue": np.linspace(1.0, 2.0, n),
            "Amplitude": np.linspace(0.5, 1.5, n),
            "HSTResDrift": np.sin(np.linspace(0, np.pi, n)),
            "WVI": np.random.default_rng(42).uniform(0.0, 1.0, n),
        }
    )


# ---------------------------------------------------------------------------
# _safe_col
# ---------------------------------------------------------------------------


class TestSafeCol:
    def test_existing_column_returned(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        s = _safe_col(df, "x")
        assert list(s) == pytest.approx([1.0, 2.0, 3.0])

    def test_missing_column_returns_default(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        s = _safe_col(df, "missing", default=99.0)
        assert all(v == 99.0 for v in s)

    def test_missing_column_same_length(self):
        df = pd.DataFrame({"a": range(5)})
        s = _safe_col(df, "nope")
        assert len(s) == 5

    def test_fills_nan_with_default(self):
        df = pd.DataFrame({"x": [1.0, float("nan"), 3.0]})
        s = _safe_col(df, "x", default=0.0)
        assert not s.isna().any()


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_constant_series_returns_zero(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = _normalize(s)
        assert (result == 0.0).all()

    def test_output_in_0_1_range(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _normalize(s)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_min_maps_to_0(self):
        s = pd.Series([10.0, 20.0, 30.0])
        result = _normalize(s)
        assert result.iloc[0] == pytest.approx(0.0)

    def test_max_maps_to_1(self):
        s = pd.Series([10.0, 20.0, 30.0])
        result = _normalize(s)
        assert result.iloc[-1] == pytest.approx(1.0)

    def test_inf_treated_as_nan(self):
        s = pd.Series([1.0, float("inf"), 3.0])
        result = _normalize(s)
        # Should not raise, inf → nan → filled with 0
        assert not result.isna().any()

    def test_negative_inf_treated_as_nan(self):
        s = pd.Series([1.0, float("-inf"), 3.0])
        result = _normalize(s)
        assert not result.isna().any()


# ---------------------------------------------------------------------------
# compute_memory_fields
# ---------------------------------------------------------------------------


class TestComputeMemoryFields:
    def test_empty_df_returned_unchanged(self):
        df = pd.DataFrame()
        result = compute_memory_fields(df)
        assert result.empty

    def test_output_has_required_columns(self):
        df = _base_df(20)
        result = compute_memory_fields(df)
        for col in ("EventIntensity", "MemoryCharge", "Afterglow", "MemoryPhase"):
            assert col in result.columns, f"Missing column: {col}"

    def test_event_intensity_in_0_1(self):
        df = _base_df(20)
        result = compute_memory_fields(df)
        ei = result["EventIntensity"]
        assert ei.min() >= -1e-9
        assert ei.max() <= 1.0 + 1e-9

    def test_afterglow_in_0_1(self):
        df = _base_df(20)
        result = compute_memory_fields(df)
        ag = result["Afterglow"]
        assert ag.min() >= -1e-9
        assert ag.max() <= 1.0 + 1e-9

    def test_memory_charge_non_negative(self):
        df = _base_df(20)
        result = compute_memory_fields(df)
        assert (result["MemoryCharge"] >= 0).all()

    def test_memory_phase_valid_labels(self):
        df = _base_df(20)
        result = compute_memory_fields(df)
        valid = {"QUIET", "ACTIVE", "DECAY"}
        assert set(result["MemoryPhase"]).issubset(valid)

    def test_does_not_mutate_input(self):
        df = _base_df(20)
        cols_before = set(df.columns)
        compute_memory_fields(df)
        assert set(df.columns) == cols_before

    def test_single_row_does_not_crash(self):
        df = _base_df(1)
        result = compute_memory_fields(df)
        # Should produce output with required columns even for 1 row
        assert "MemoryPhase" in result.columns

    def test_missing_physics_columns_handled(self):
        """Only a Date column — all physics columns absent → defaults used."""
        df = pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=10, freq="D")})
        result = compute_memory_fields(df)
        assert "EventIntensity" in result.columns

    def test_no_date_column_still_works(self):
        """Without Date, physics-only mode runs without crashing."""
        df = pd.DataFrame(
            {
                "ResonanceValue": np.linspace(1.0, 2.0, 15),
                "Amplitude": np.linspace(0.5, 1.0, 15),
                "HSTResDrift": np.zeros(15),
                "WVI": np.zeros(15),
            }
        )
        result = compute_memory_fields(df)
        assert "EventIntensity" in result.columns

    def test_row_count_preserved(self):
        n = 30
        df = _base_df(n)
        result = compute_memory_fields(df)
        assert len(result) == n
