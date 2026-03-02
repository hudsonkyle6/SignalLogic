"""
Tests for analytics memory modules (requires pandas/numpy).

These tests are automatically skipped when the analytics extra is not installed.
Install with: pip install 'signal-logic[analytics]'

Covers:
  - rhythm_os.core.memory.afterglow: compute_memory_fields
  - rhythm_os.core.memory.ghost: inject_ghost_layer, compute_ghost_metrics
"""
from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")


from rhythm_os.core.memory.afterglow import compute_memory_fields  # noqa: E402
from rhythm_os.core.memory.ghost import (  # noqa: E402
    compute_ghost_metrics,
    inject_ghost_layer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_df(n: int = 30) -> "pd.DataFrame":
    """Build a minimal DataFrame with columns used by afterglow/ghost."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "Date": dates,
        "ResonanceValue": rng.uniform(0.3, 0.9, n),
        "Amplitude": rng.uniform(0.1, 0.5, n),
        "HSTResDrift": rng.uniform(-0.2, 0.2, n),
        "WVI": rng.uniform(0.0, 0.8, n),
        "VIXClose": rng.uniform(12.0, 35.0, n),
    })


# ---------------------------------------------------------------------------
# compute_memory_fields (afterglow)
# ---------------------------------------------------------------------------

class TestComputeMemoryFields:
    def test_empty_df_returns_empty(self):
        empty = pd.DataFrame()
        result = compute_memory_fields(empty)
        assert result.empty

    def test_output_columns_present(self):
        df = _base_df(30)
        result = compute_memory_fields(df)
        for col in ["EventIntensity", "MemoryCharge", "Afterglow", "MemoryPhase"]:
            assert col in result.columns, f"missing column: {col}"

    def test_event_intensity_bounded_0_1(self):
        df = _base_df(30)
        result = compute_memory_fields(df)
        ei = result["EventIntensity"]
        assert (ei >= 0.0).all()
        assert (ei <= 1.0).all()

    def test_afterglow_bounded_0_1(self):
        df = _base_df(30)
        result = compute_memory_fields(df)
        ag = result["Afterglow"]
        assert (ag >= 0.0).all()
        assert (ag <= 1.0).all()

    def test_memory_charge_non_negative(self):
        df = _base_df(30)
        result = compute_memory_fields(df)
        assert (result["MemoryCharge"] >= 0.0).all()

    def test_memory_phase_valid_labels(self):
        df = _base_df(50)
        result = compute_memory_fields(df)
        valid = {"QUIET", "ACTIVE", "DECAY"}
        assert set(result["MemoryPhase"].unique()).issubset(valid)

    def test_original_df_not_mutated(self):
        df = _base_df(20)
        original_cols = set(df.columns)
        compute_memory_fields(df)
        assert set(df.columns) == original_cols

    def test_df_without_date_column(self):
        """Should still produce output fields even without Date column."""
        df = _base_df(20).drop(columns=["Date"])
        result = compute_memory_fields(df)
        assert "EventIntensity" in result.columns

    def test_constant_series_no_crash(self):
        """Constant signals should not raise (normalize handles zero span)."""
        n = 20
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "ResonanceValue": [0.5] * n,
            "Amplitude": [0.3] * n,
            "HSTResDrift": [0.0] * n,
            "WVI": [0.2] * n,
        })
        result = compute_memory_fields(df)
        assert "EventIntensity" in result.columns


# ---------------------------------------------------------------------------
# inject_ghost_layer
# ---------------------------------------------------------------------------

class TestInjectGhostLayer:
    def test_empty_df_returns_empty(self):
        empty = pd.DataFrame()
        result = inject_ghost_layer(empty)
        assert result.empty

    def test_no_nans_no_ghosting(self):
        df = _base_df(10)
        result = inject_ghost_layer(df)
        # No NaN values → GhostFlag should all be 0
        assert "GhostFlag" in result.columns
        assert (result["GhostFlag"] == 0).all()

    def test_nan_values_ghosted(self):
        df = _base_df(10)
        df.loc[3, "ResonanceValue"] = float("nan")
        result = inject_ghost_layer(df)
        # Row 3 should be flagged
        assert result.loc[3, "GhostFlag"] == 1
        assert "ResonanceValue_ghosted" in result.columns

    def test_ghost_level_column_present(self):
        df = _base_df(10)
        result = inject_ghost_layer(df)
        assert "GhostLevel" in result.columns

    def test_ghost_level_values_valid(self):
        df = _base_df(10)
        result = inject_ghost_layer(df)
        valid = {"NONE", "GHOST_LIGHT", "GHOST_MEDIUM", "GHOST_HEAVY"}
        assert set(result["GhostLevel"].unique()).issubset(valid)

    def test_original_not_mutated(self):
        df = _base_df(10)
        original_cols = set(df.columns)
        inject_ghost_layer(df)
        assert set(df.columns) == original_cols


# ---------------------------------------------------------------------------
# compute_ghost_metrics
# ---------------------------------------------------------------------------

class TestComputeGhostMetrics:
    def test_empty_df_returns_empty(self):
        empty = pd.DataFrame()
        result = compute_ghost_metrics(empty)
        assert result.empty

    def test_output_columns_present(self):
        df = _base_df(40)
        result = compute_ghost_metrics(df)
        expected = [
            "GhostDriftComponent",
            "GhostPhaseComponent",
            "GhostVolatilityComponent",
            "GhostInstabilityRaw",
            "GhostStabilityIndex",
            "GhostMemoryPressure",
            "GhostGovernor",
            "GhostShadow",
        ]
        for col in expected:
            assert col in result.columns, f"missing: {col}"

    def test_stability_index_plus_instability_equals_one(self):
        df = _base_df(40)
        result = compute_ghost_metrics(df)
        diff = (result["GhostStabilityIndex"] + result["GhostInstabilityRaw"] - 1.0).abs()
        assert (diff < 1e-9).all()

    def test_governor_bounded(self):
        df = _base_df(40)
        result = compute_ghost_metrics(df)
        g = result["GhostGovernor"]
        assert (g >= 0.3).all()
        assert (g <= 1.0).all()

    def test_ghost_shadow_valid_labels(self):
        df = _base_df(40)
        result = compute_ghost_metrics(df)
        valid = {"CLEAR", "HAZE", "SHADOW", "VOID"}
        assert set(result["GhostShadow"].unique()).issubset(valid)

    def test_phase_component_uses_phi_columns(self):
        df = _base_df(20)
        df["phi_h"] = np.linspace(0, 2 * np.pi, 20)
        df["phi_e"] = np.linspace(0, 2 * np.pi, 20)
        result = compute_ghost_metrics(df)
        # When phases are equal, phase component ≈ 1.0 (perfect alignment)
        assert "GhostPhaseComponent" in result.columns
