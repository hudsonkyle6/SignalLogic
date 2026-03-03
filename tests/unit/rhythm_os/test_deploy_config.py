"""
Tests for rhythm_os.runtime.deploy_config

Modules covered:
- _find_config              (config file discovery)
- _load                     (YAML loading with caching)
- get_config                (full config dict accessor)
- get_location              (lat/lon/label accessor)
- get_deployment_name       (deployment name accessor)
- get_domain_channels       (channel list accessor)
- get_baseline_requirements (baseline min counts accessor)

Invariants:
- All getters return safe defaults when config has no relevant keys
- SIGNALLOGIC_CONFIG env var overrides file discovery
- _load is cached — file is only read once per process
- get_location returns (float, float, str)
- get_baseline_requirements returns dict with min_meter_cycles and min_natural_records
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_cache(mod):
    """Reset the module-level cache so each test gets a fresh load."""
    mod._cache = None


def _write_yaml(tmp_path, content: dict, name: str = "deployment.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.dump(content))
    return p


def _empty_config(tmp_path, monkeypatch, mod):
    """Set up an empty {} config and reset cache."""
    p = _write_yaml(tmp_path, {})
    monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
    _reset_cache(mod)


# ---------------------------------------------------------------------------
# get_location — defaults and overrides
# ---------------------------------------------------------------------------


class TestGetLocation:
    def test_returns_three_tuple(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        result = cfg.get_location()
        assert len(result) == 3

    def test_default_types(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        lat, lon, label = cfg.get_location()
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert isinstance(label, str)

    def test_reads_lat_lon_label_from_yaml(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        p = _write_yaml(
            tmp_path, {"location": {"lat": 12.34, "lon": 56.78, "label": "Test City"}}
        )
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
        _reset_cache(cfg)
        lat, lon, label = cfg.get_location()
        assert lat == pytest.approx(12.34)
        assert lon == pytest.approx(56.78)
        assert label == "Test City"


# ---------------------------------------------------------------------------
# get_deployment_name
# ---------------------------------------------------------------------------


class TestGetDeploymentName:
    def test_default_is_signallogic(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        assert cfg.get_deployment_name() == "SignalLogic"

    def test_reads_name_from_yaml(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        p = _write_yaml(tmp_path, {"deployment": {"name": "MyDeploy"}})
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
        _reset_cache(cfg)
        assert cfg.get_deployment_name() == "MyDeploy"


# ---------------------------------------------------------------------------
# get_domain_channels
# ---------------------------------------------------------------------------


class TestGetDomainChannels:
    def test_default_is_empty_list(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        assert cfg.get_domain_channels() == []

    def test_reads_channels_from_yaml(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        p = _write_yaml(tmp_path, {"domain": {"channels": ["weather", "tides"]}})
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
        _reset_cache(cfg)
        channels = cfg.get_domain_channels()
        assert "weather" in channels
        assert "tides" in channels


# ---------------------------------------------------------------------------
# get_baseline_requirements
# ---------------------------------------------------------------------------


class TestGetBaselineRequirements:
    def test_returns_dict_with_expected_keys(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        result = cfg.get_baseline_requirements()
        assert "min_meter_cycles" in result
        assert "min_natural_records" in result

    def test_defaults_are_ints(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        result = cfg.get_baseline_requirements()
        assert isinstance(result["min_meter_cycles"], int)
        assert isinstance(result["min_natural_records"], int)

    def test_reads_from_yaml(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        p = _write_yaml(
            tmp_path, {"baseline": {"min_meter_cycles": 10, "min_natural_records": 2}}
        )
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
        _reset_cache(cfg)
        result = cfg.get_baseline_requirements()
        assert result["min_meter_cycles"] == 10
        assert result["min_natural_records"] == 2


# ---------------------------------------------------------------------------
# _load — caching and error handling
# ---------------------------------------------------------------------------


class TestLoad:
    def test_returns_dict(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        assert isinstance(cfg._load(), dict)

    def test_empty_yaml_gives_empty_dict(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        assert cfg._load() == {}

    def test_missing_file_gives_empty_dict(self, monkeypatch):
        """When _find_config returns None, _load returns {}."""
        import rhythm_os.runtime.deploy_config as cfg

        monkeypatch.setattr(cfg, "_find_config", lambda: None)
        _reset_cache(cfg)
        assert cfg._load() == {}

    def test_cached_after_first_call(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        first = cfg._load()
        second = cfg._load()
        assert first is second

    def test_bad_yaml_returns_empty_dict(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        bad_yaml = tmp_path / "deployment.yaml"
        bad_yaml.write_text("{ invalid yaml: [unclosed")
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(bad_yaml))
        _reset_cache(cfg)
        result = cfg._load()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_config
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_returns_dict(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        _empty_config(tmp_path, monkeypatch, cfg)
        assert isinstance(cfg.get_config(), dict)

    def test_returns_full_config_dict(self, monkeypatch, tmp_path):
        import rhythm_os.runtime.deploy_config as cfg

        content = {"deployment": {"name": "X"}, "location": {"lat": 1.0, "lon": 2.0}}
        p = _write_yaml(tmp_path, content)
        monkeypatch.setenv("SIGNALLOGIC_CONFIG", str(p))
        _reset_cache(cfg)
        result = cfg.get_config()
        assert "deployment" in result
        assert "location" in result
