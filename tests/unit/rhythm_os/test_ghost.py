"""
Tests for rhythm_os.core.memory.ghost

Modules covered:
- inject_ghost_layer   (gap-filling with ghost values)
- _sigmoid             (sigmoid helper)
- _normalize           (0-1 normalization helper)
- _angle_wrap          (angular wrapping helper)
- compute_ghost_metrics (full ghost engine)

Invariants:
- inject_ghost_layer is safe on empty DataFrames
- inject_ghost_layer does not modify columns with no NaN gaps
- inject_ghost_layer adds *_ghosted columns for cols with NaN
- GhostLevel is one of NONE, GHOST_LIGHT, GHOST_MEDIUM, GHOST_HEAVY
- compute_ghost_metrics produces all required output columns
- GhostStabilityIndex = 1 - GhostInstabilityRaw
- GhostShadow is one of CLEAR, HAZE, SHADOW, VOID
- GhostGovernor is clipped to [0.3, 1.0]
"""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from rhythm_os.core.memory.ghost import (  # noqa: E402
    inject_ghost_layer,
    compute_ghost_metrics,
    _sigmoid,
    _normalize,
    _angle_wrap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_ghost_df(n: int = 30) -> "pd.DataFrame":
    """DataFrame with the columns compute_ghost_metrics expects."""
    rng = np.random.default_rng(0)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Date": dates,
            "HSTResDrift": rng.normal(0, 0.5, n),
            "VIXClose": rng.uniform(15.0, 30.0, n),
            "WVI": rng.uniform(0.0, 0.8, n),
            "Amplitude": rng.uniform(0.3, 0.9, n),
            "MemoryCharge": rng.uniform(0.0, 1.0, n),
            "Afterglow": rng.uniform(0.0, 1.0, n),
        }
    )


# ---------------------------------------------------------------------------
# _sigmoid
# ---------------------------------------------------------------------------


class TestSigmoid:
    def test_zero_input_returns_half(self):
        result = _sigmoid(np.array([0.0]))
        assert result[0] == pytest.approx(0.5)

    def test_large_positive_approaches_one(self):
        result = _sigmoid(np.array([100.0]))
        assert result[0] > 0.99

    def test_large_negative_approaches_zero(self):
        result = _sigmoid(np.array([-100.0]))
        assert result[0] < 0.01

    def test_output_in_0_1(self):
        x = np.linspace(-10, 10, 50)
        result = _sigmoid(x)
        assert (result >= 0.0).all()
        assert (result <= 1.0).all()


# ---------------------------------------------------------------------------
# _normalize (ghost version with explicit vmin/vmax)
# ---------------------------------------------------------------------------


class TestNormalizeGhost:
    def test_constant_series_returns_half(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = _normalize(s, 5.0, 5.0)
        assert (result == 0.5).all()

    def test_min_val_maps_to_0(self):
        s = pd.Series([0.0, 0.5, 1.0])
        result = _normalize(s, 0.0, 1.0)
        assert result.iloc[0] == pytest.approx(0.0)

    def test_max_val_maps_to_1(self):
        s = pd.Series([0.0, 0.5, 1.0])
        result = _normalize(s, 0.0, 1.0)
        assert result.iloc[-1] == pytest.approx(1.0)

    def test_clipped_to_0_1(self):
        s = pd.Series([-1.0, 0.5, 2.0])
        result = _normalize(s, 0.0, 1.0)
        assert result.min() >= 0.0
        assert result.max() <= 1.0


# ---------------------------------------------------------------------------
# _angle_wrap
# ---------------------------------------------------------------------------


class TestAngleWrap:
    def test_zero_stays_zero(self):
        assert _angle_wrap(0.0) == pytest.approx(0.0)

    def test_pi_maps_to_negative_pi(self):
        # (pi + pi) % 2pi - pi = 2pi % 2pi - pi = 0 - pi = -pi
        result = _angle_wrap(np.pi)
        assert abs(result) == pytest.approx(np.pi)

    def test_2pi_maps_to_zero(self):
        result = _angle_wrap(2 * np.pi)
        assert abs(result) < 1e-9 or abs(result - 2 * np.pi) < 1e-9

    def test_output_in_neg_pi_to_pi(self):
        for angle in np.linspace(-4 * np.pi, 4 * np.pi, 100):
            result = _angle_wrap(angle)
            assert -np.pi <= result <= np.pi


# ---------------------------------------------------------------------------
# inject_ghost_layer
# ---------------------------------------------------------------------------


class TestInjectGhostLayer:
    def test_empty_df_returned_unchanged(self):
        df = pd.DataFrame()
        result = inject_ghost_layer(df)
        assert result.empty

    def test_no_nan_no_ghosted_columns(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [1.0, 2.0, 3.0],
                "Amplitude": [0.5, 0.6, 0.7],
                "Afterglow": [0.1, 0.2, 0.3],
            }
        )
        result = inject_ghost_layer(df)
        # No NaN → no ghosted columns added
        assert "ResonanceValue_ghosted" not in result.columns

    def test_nan_produces_ghosted_column(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [1.0, float("nan"), 3.0],
                "Afterglow": [0.5, 0.5, 0.5],
            }
        )
        result = inject_ghost_layer(df)
        assert "ResonanceValue_ghosted" in result.columns

    def test_ghost_flag_set_for_nan_rows(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [1.0, float("nan"), 3.0],
                "Afterglow": [0.5, 0.5, 0.5],
            }
        )
        result = inject_ghost_layer(df)
        assert result["GhostFlag"].iloc[1] == 1

    def test_ghost_flag_zero_for_clean_rows(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [1.0, float("nan"), 3.0],
                "Afterglow": [0.5, 0.5, 0.5],
            }
        )
        result = inject_ghost_layer(df)
        assert result["GhostFlag"].iloc[0] == 0

    def test_ghost_level_none_for_clean_rows(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [1.0, 2.0, 3.0],
                "Afterglow": [0.5, 0.5, 0.5],
            }
        )
        result = inject_ghost_layer(df)
        assert (result["GhostLevel"] == "NONE").all()

    def test_ghost_level_labels_valid(self):
        df = pd.DataFrame(
            {
                "ResonanceValue": [float("nan")] * 3,
                "Afterglow": [0.1, 0.5, 0.9],
            }
        )
        result = inject_ghost_layer(df)
        valid = {"NONE", "GHOST_LIGHT", "GHOST_MEDIUM", "GHOST_HEAVY"}
        assert set(result["GhostLevel"]).issubset(valid)

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({"ResonanceValue": [1.0, float("nan"), 3.0]})
        cols_before = set(df.columns)
        inject_ghost_layer(df)
        assert set(df.columns) == cols_before

    def test_missing_ghost_cols_skipped_silently(self):
        """Columns not in ghost_cols list are not processed."""
        df = pd.DataFrame({"SomeOtherCol": [1.0, float("nan"), 3.0]})
        result = inject_ghost_layer(df)
        # No ghosted column added for unknown column
        assert "SomeOtherCol_ghosted" not in result.columns


# ---------------------------------------------------------------------------
# compute_ghost_metrics
# ---------------------------------------------------------------------------


class TestComputeGhostMetrics:
    def test_empty_df_returned_unchanged(self):
        df = pd.DataFrame()
        result = compute_ghost_metrics(df)
        assert result.empty

    def test_output_has_required_columns(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        required = [
            "GhostDriftComponent",
            "GhostPhaseComponent",
            "GhostVolatilityComponent",
            "GhostInstabilityRaw",
            "GhostStabilityIndex",
            "GhostMemoryPressure",
            "GhostGovernor",
            "GhostShadow",
        ]
        for col in required:
            assert col in result.columns, f"Missing column: {col}"

    def test_stability_index_complement_of_instability(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        diff = (
            result["GhostInstabilityRaw"] + result["GhostStabilityIndex"] - 1.0
        ).abs()
        assert diff.max() < 1e-9

    def test_ghost_shadow_valid_labels(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        valid = {"CLEAR", "HAZE", "SHADOW", "VOID"}
        assert set(result["GhostShadow"]).issubset(valid)

    def test_ghost_governor_clipped(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        assert result["GhostGovernor"].min() >= 0.3 - 1e-9
        assert result["GhostGovernor"].max() <= 1.0 + 1e-9

    def test_instability_in_0_1(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        assert result["GhostInstabilityRaw"].min() >= -1e-9
        assert result["GhostInstabilityRaw"].max() <= 1.0 + 1e-9

    def test_without_phi_columns_uses_default_phase(self):
        """Without phi_h and phi_e, GhostPhaseComponent defaults to 0.5."""
        df = _base_ghost_df(30)
        assert "phi_h" not in df.columns
        result = compute_ghost_metrics(df)
        assert (result["GhostPhaseComponent"] == 0.5).all()

    def test_with_phi_columns_computes_phase(self):
        df = _base_ghost_df(30)
        df["phi_h"] = np.linspace(0, np.pi, 30)
        df["phi_e"] = np.linspace(np.pi, 0, 30)
        result = compute_ghost_metrics(df)
        # Should not all be 0.5 when phi columns are provided
        assert not (result["GhostPhaseComponent"] == 0.5).all()

    def test_memory_charge_eff_produced(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        assert "MemoryChargeEff" in result.columns

    def test_afterglow_eff_produced(self):
        df = _base_ghost_df(30)
        result = compute_ghost_metrics(df)
        assert "AfterglowEff" in result.columns

    def test_without_memory_charge_eff_is_nan(self):
        df = _base_ghost_df(30).drop(columns=["MemoryCharge"])
        result = compute_ghost_metrics(df)
        assert result["MemoryChargeEff"].isna().all()

    def test_without_afterglow_eff_is_nan(self):
        df = _base_ghost_df(30).drop(columns=["Afterglow"])
        result = compute_ghost_metrics(df)
        assert result["AfterglowEff"].isna().all()

    def test_does_not_mutate_input(self):
        df = _base_ghost_df(30)
        cols_before = set(df.columns)
        compute_ghost_metrics(df)
        assert set(df.columns) == cols_before
