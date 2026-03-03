"""
Tests for rhythm_os.scope.scope_run_once

Modules covered:
- load_waves  (loads sealed Waves from penstock)
- main        (configure, load, render pipeline)

Invariants:
- load_waves returns [] when penstock dir does not exist
- load_waves returns a list of waves when penstock dir exists
- main() calls render_scope with the loaded waves
- main() does not crash on empty penstock
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock


class TestLoadWaves:
    def test_returns_empty_when_dir_missing(self, monkeypatch, tmp_path):
        import rhythm_os.scope.scope_run_once as mod

        nonexistent = tmp_path / "penstock_missing"
        monkeypatch.setattr(mod, "PENSTOCK_DIR", nonexistent)
        result = mod.load_waves()
        assert result == []

    def test_returns_list_when_dir_exists(self, monkeypatch, tmp_path):
        import rhythm_os.scope.scope_run_once as mod

        penstock = tmp_path / "penstock"
        penstock.mkdir()
        monkeypatch.setattr(mod, "PENSTOCK_DIR", penstock)

        fake_wave = MagicMock()
        with patch.object(mod, "load_penstock", return_value=[fake_wave]):
            result = mod.load_waves()
        assert result == [fake_wave]

    def test_empty_dir_returns_empty_list(self, monkeypatch, tmp_path):
        import rhythm_os.scope.scope_run_once as mod

        penstock = tmp_path / "penstock"
        penstock.mkdir()
        monkeypatch.setattr(mod, "PENSTOCK_DIR", penstock)

        with patch.object(mod, "load_penstock", return_value=[]):
            result = mod.load_waves()
        assert result == []


class TestMain:
    def test_main_does_not_crash(self, monkeypatch, tmp_path):
        import rhythm_os.scope.scope_run_once as mod

        penstock = tmp_path / "penstock"
        penstock.mkdir()
        monkeypatch.setattr(mod, "PENSTOCK_DIR", penstock)

        with (
            patch.object(mod, "load_penstock", return_value=[]),
            patch.object(mod, "render_scope") as mock_render,
        ):
            mod.main()
        mock_render.assert_called_once()

    def test_main_passes_waves_to_render_scope(self, monkeypatch, tmp_path):
        import rhythm_os.scope.scope_run_once as mod

        penstock = tmp_path / "penstock"
        penstock.mkdir()
        monkeypatch.setattr(mod, "PENSTOCK_DIR", penstock)

        fake_waves = [MagicMock(), MagicMock()]
        with (
            patch.object(mod, "load_penstock", return_value=fake_waves),
            patch.object(mod, "render_scope") as mock_render,
        ):
            mod.main()

        called_waves = mock_render.call_args[0][0]
        assert list(called_waves) == fake_waves
