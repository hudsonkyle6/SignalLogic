"""
Tests for rhythm_os.runtime.paths

Invariants:
- All path constants are absolute (not relative to working directory)
- All paths are under the same DATA_DIR root
- Paths are consistent with each other (no cross-root references)
- The module is importable from any working directory
"""

from __future__ import annotations


from rhythm_os.runtime.paths import (
    DATA_DIR,
    PENSTOCK_DIR,
    TURBINE_DIR,
    QUEUE_PATH,
    BUS_DIR,
    NATURAL_DIR,
    MANDATES_DIR,
)


class TestPathsAbsolute:
    def test_data_dir_is_absolute(self):
        assert DATA_DIR.is_absolute()

    def test_penstock_dir_is_absolute(self):
        assert PENSTOCK_DIR.is_absolute()

    def test_turbine_dir_is_absolute(self):
        assert TURBINE_DIR.is_absolute()

    def test_queue_path_is_absolute(self):
        assert QUEUE_PATH.is_absolute()

    def test_bus_dir_is_absolute(self):
        assert BUS_DIR.is_absolute()

    def test_natural_dir_is_absolute(self):
        assert NATURAL_DIR.is_absolute()

    def test_mandates_dir_is_absolute(self):
        assert MANDATES_DIR.is_absolute()


class TestPathsConsistency:
    def test_penstock_under_data_dir(self):
        assert str(PENSTOCK_DIR).startswith(str(DATA_DIR))

    def test_turbine_under_data_dir(self):
        assert str(TURBINE_DIR).startswith(str(DATA_DIR))

    def test_queue_under_data_dir(self):
        assert str(QUEUE_PATH).startswith(str(DATA_DIR))

    def test_bus_under_data_dir(self):
        assert str(BUS_DIR).startswith(str(DATA_DIR))

    def test_penstock_and_turbine_are_different(self):
        assert PENSTOCK_DIR != TURBINE_DIR

    def test_queue_is_jsonl(self):
        assert QUEUE_PATH.suffix == ".jsonl"

    def test_turbine_not_penstock(self):
        # The turbine basin must not be the same as the penstock
        assert "turbine" in str(TURBINE_DIR)
        assert "penstock" in str(PENSTOCK_DIR)

    def test_paths_within_rhythm_os_src(self):
        # All data paths should be within the rhythm_os package tree
        assert "rhythm_os" in str(DATA_DIR)
