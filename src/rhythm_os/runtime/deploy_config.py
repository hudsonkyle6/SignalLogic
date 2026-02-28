"""
Deployment configuration reader.

Reads deployment.yaml — searched by walking up from this file's location,
or from the path in the SIGNALLOGIC_CONFIG environment variable.

All values have safe defaults so the system runs without any config file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

_CONFIG_ENV = "SIGNALLOGIC_CONFIG"
_CONFIG_FILENAME = "deployment.yaml"

_DEFAULT_LAT: float = 42.9876
_DEFAULT_LON: float = -71.8126
_DEFAULT_LABEL: str = "Southern NH"


def _find_config() -> Optional[Path]:
    env = os.environ.get(_CONFIG_ENV)
    if env:
        p = Path(env)
        if p.exists():
            return p
    # Walk up from this file's location until we find deployment.yaml
    for parent in Path(__file__).resolve().parents:
        candidate = parent / _CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return None


_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    path = _find_config()
    if path is None:
        _cache = {}
        return _cache
    try:
        with path.open("r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f) or {}
    except Exception:
        _cache = {}
    return _cache


def get_config() -> Dict[str, Any]:
    """Return the full deployment config dict."""
    return _load()


def get_location() -> Tuple[float, float, str]:
    """Return (lat, lon, label) for this deployment."""
    loc = _load().get("location", {})
    lat = float(loc.get("lat", _DEFAULT_LAT))
    lon = float(loc.get("lon", _DEFAULT_LON))
    label = str(loc.get("label", _DEFAULT_LABEL))
    return lat, lon, label


def get_deployment_name() -> str:
    return str(_load().get("deployment", {}).get("name", "SignalLogic"))


def get_domain_channels() -> List[str]:
    return list(_load().get("domain", {}).get("channels", []))


def get_baseline_requirements() -> Dict[str, int]:
    b = _load().get("baseline", {})
    return {
        "min_meter_cycles": int(b.get("min_meter_cycles", 30)),
        "min_natural_records": int(b.get("min_natural_records", 4)),
    }
