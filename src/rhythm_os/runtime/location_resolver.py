"""
Location Resolver — Runtime position detection.

Resolves the current deployment location at call time rather than
relying on a static deployment.yaml entry. Useful when running on
a machine that travels (laptop, Mac Pro, etc.).

Resolution order:
  1. SIGNALLOGIC_LAT / SIGNALLOGIC_LON env vars (explicit override)
  2. IP geolocation via ipinfo.io (no API key, city-level accuracy)
  3. IP geolocation via ip-api.com (fallback if ipinfo fails)
  4. deployment.yaml static config (offline fallback)

Returns (lat, lon, label) — same signature as deploy_config.get_location().
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import requests

from rhythm_os.runtime.deploy_config import get_location as _static_location


_TIMEOUT = 5  # seconds — fast fail, don't block the cycle


def _try_ipinfo() -> Optional[Tuple[float, float, str]]:
    """ipinfo.io free tier — returns {"loc": "lat,lon", "city": "...", ...}"""
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        loc = data.get("loc", "")
        if "," not in loc:
            return None
        lat_s, lon_s = loc.split(",", 1)
        lat = float(lat_s.strip())
        lon = float(lon_s.strip())
        city = data.get("city", "")
        region = data.get("region", "")
        label = f"{city}, {region}".strip(", ") or "IP-resolved"
        return lat, lon, label
    except Exception:
        return None


def _try_ipapi() -> Optional[Tuple[float, float, str]]:
    """ip-api.com free tier — returns {"lat": ..., "lon": ..., "city": ...}"""
    try:
        resp = requests.get("http://ip-api.com/json", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return None
        lat = float(data["lat"])
        lon = float(data["lon"])
        city = data.get("city", "")
        region = data.get("regionName", "")
        label = f"{city}, {region}".strip(", ") or "IP-resolved"
        return lat, lon, label
    except Exception:
        return None


def resolve_location() -> Tuple[float, float, str]:
    """
    Return (lat, lon, label) for the current runtime location.

    Always call this inside a function body — never at module level —
    so the position is resolved fresh each cycle.
    """
    # 1. Explicit env override
    lat_env = os.environ.get("SIGNALLOGIC_LAT")
    lon_env = os.environ.get("SIGNALLOGIC_LON")
    if lat_env and lon_env:
        try:
            label = os.environ.get("SIGNALLOGIC_LABEL", "env-override")
            return float(lat_env), float(lon_env), label
        except ValueError:
            pass

    # 2. IP geolocation (primary)
    result = _try_ipinfo()
    if result:
        return result

    # 3. IP geolocation (fallback)
    result = _try_ipapi()
    if result:
        return result

    # 4. Static config
    return _static_location()
