"""
Location Resolver — Runtime position detection.

Resolves the current deployment location at call time rather than
relying on a static deployment.yaml entry. Useful when running on
a machine that travels (laptop, Mac Pro, etc.).

Resolution order:
  1. SIGNALLOGIC_LAT / SIGNALLOGIC_LON env vars (explicit override)
  2. IP geolocation via ipinfo.io (no API key, city-level accuracy)
  3. IP geolocation via ip-api.com (fallback if ipinfo fails)
  4. IP geolocation via ipapi.co (second fallback)
  5. deployment.yaml static config (offline fallback)

Returns (lat, lon, label) — same signature as deploy_config.get_location().
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Optional, Tuple

from rhythm_os.runtime.deploy_config import get_location as _static_location


_TIMEOUT = 5  # seconds — fast fail, don't block the cycle
_log = logging.getLogger(__name__)


def _fetch_json(url: str) -> Optional[dict]:
    """Fetch JSON from url using stdlib urllib (no external deps)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SignalLogic/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        _log.debug("location fetch failed url=%s err=%s", url, exc)
        return None


def _try_ipinfo() -> Optional[Tuple[float, float, str]]:
    """ipinfo.io free tier — returns {"loc": "lat,lon", "city": "...", ...}"""
    data = _fetch_json("https://ipinfo.io/json")
    if not data:
        return None
    loc = data.get("loc", "")
    if "," not in loc:
        return None
    lat_s, lon_s = loc.split(",", 1)
    try:
        lat = float(lat_s.strip())
        lon = float(lon_s.strip())
    except ValueError:
        return None
    city = data.get("city", "")
    region = data.get("region", "")
    label = f"{city}, {region}".strip(", ") or "IP-resolved"
    return lat, lon, label


def _try_ipapi() -> Optional[Tuple[float, float, str]]:
    """ip-api.com free tier — returns {"lat": ..., "lon": ..., "city": ...}"""
    data = _fetch_json("http://ip-api.com/json")
    if not data or data.get("status") != "success":
        return None
    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (KeyError, ValueError):
        return None
    city = data.get("city", "")
    region = data.get("regionName", "")
    label = f"{city}, {region}".strip(", ") or "IP-resolved"
    return lat, lon, label


def _try_ipapico() -> Optional[Tuple[float, float, str]]:
    """ipapi.co free tier — returns {"latitude": ..., "longitude": ..., "city": ...}"""
    data = _fetch_json("https://ipapi.co/json/")
    if not data:
        return None
    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (KeyError, ValueError):
        return None
    city = data.get("city", "")
    region = data.get("region", "")
    label = f"{city}, {region}".strip(", ") or "IP-resolved"
    return lat, lon, label


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
            result = float(lat_env), float(lon_env), label
            _log.debug("location resolved via env vars: %s", label)
            return result
        except ValueError:
            pass

    # 2. IP geolocation (primary)
    result = _try_ipinfo()
    if result:
        _log.debug("location resolved via ipinfo.io: %s", result[2])
        return result

    # 3. IP geolocation (fallback 1)
    result = _try_ipapi()
    if result:
        _log.debug("location resolved via ip-api.com: %s", result[2])
        return result

    # 4. IP geolocation (fallback 2)
    result = _try_ipapico()
    if result:
        _log.debug("location resolved via ipapi.co: %s", result[2])
        return result

    # 5. Static config
    static = _static_location()
    _log.warning(
        "IP geolocation unavailable — falling back to static config: %s. "
        "Set SIGNALLOGIC_LAT / SIGNALLOGIC_LON env vars to override.",
        static[2],
    )
    return static
