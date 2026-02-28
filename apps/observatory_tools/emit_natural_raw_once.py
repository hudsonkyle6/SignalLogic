from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from rhythm_os.runtime.temporal_anchor import compute_anchor, SEMI_DIURNAL_PERIOD_S
from rhythm_os.runtime.deploy_config import get_location

# ---------------------------------------------------------------------
# Observatory coordinates — loaded from deployment.yaml at startup.
# Override the file or set SIGNALLOGIC_CONFIG to change location.
# ---------------------------------------------------------------------

_lat, _lon, _label = get_location()
LAT: float = _lat
LON: float = _lon

# ---------------------------------------------------------------------
# Open-Meteo (no API key, no rate limit for reasonable use)
# ---------------------------------------------------------------------

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_PARAMS = {
    "latitude": LAT,
    "longitude": LON,
    "current": ",".join([
        "surface_pressure",
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "wind_direction_10m",
        "cloud_cover",
        "weather_code",
    ]),
    "timezone": "UTC",
    "forecast_days": 1,
}

# Pressure normalization bounds (mid-latitude surface pressure, hPa)
_P_LOW:  float = 975.0
_P_HIGH: float = 1045.0
_P_SPAN: float = _P_HIGH - _P_LOW

# Temperature normalization bounds (°C, seasonal NH range)
_T_LOW:  float = -25.0
_T_HIGH: float = 38.0
_T_SPAN: float = _T_HIGH - _T_LOW

from rhythm_os.runtime.paths import NATURAL_DIR as OUT_DIR


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _fetch_weather() -> Optional[Dict[str, Any]]:
    """
    Fetch current conditions from Open-Meteo.
    Returns the 'current' dict on success, None on any failure.
    """
    try:
        resp = requests.get(_OPEN_METEO_URL, params=_OPEN_METEO_PARAMS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("current", {})
    except Exception as exc:
        print(f"OBSERVATORY: weather fetch failed — {exc}")
        return None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _circular_diff(a: float, b: float) -> float:
    """Signed shortest arc from b to a in [0, 1] phase space. Result in [-0.5, 0.5]."""
    d = (a - b) % 1.0
    return d - 1.0 if d > 0.5 else d


def _make_record(
    t: float,
    channel: str,
    phase_external: float,
    phase_field: float,
    coherence: Optional[float],
    raw: Dict[str, Any],
    fetch_ok: bool,
) -> Dict[str, Any]:
    phase_diff = _circular_diff(phase_external, phase_field)
    return {
        "t": t,
        "domain": "natural_raw",
        "lane": "natural",
        "channel": channel,
        "field_cycle": "semi_diurnal" if channel == "helix_projection" else "diurnal",
        "window_s": SEMI_DIURNAL_PERIOD_S if channel == "helix_projection" else 86400.0,
        "data": {
            "phase_external": phase_external,
            "phase_field": phase_field,
            "phase_diff": phase_diff,
            "coherence": coherence,
        },
        "raw": raw,
        "extractor": {
            "source": "open_meteo",
            "lat": LAT,
            "lon": LON,
            "runner": "emit_natural_raw_once",
            "version": "v2",
            "fetch_ok": fetch_ok,
        },
    }


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    t_now = float(time.time())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.jsonl"

    anchor = compute_anchor(t_now, domain="natural")
    weather = _fetch_weather()
    fetch_ok = weather is not None

    if fetch_ok:
        pressure_hpa  = float(weather.get("surface_pressure", 1013.25))
        temperature_c = float(weather.get("temperature_2m", 10.0))
        humidity_pct  = float(weather.get("relative_humidity_2m", 60.0))
        wind_speed    = float(weather.get("wind_speed_10m", 0.0))
        wind_dir      = float(weather.get("wind_direction_10m", 0.0))
        cloud_cover   = float(weather.get("cloud_cover", 50.0))
        weather_code  = int(weather.get("weather_code", 0))
        coherence_pressure = 0.85
        coherence_thermal  = 0.85
    else:
        # Fallback: write a low-coherence stub so the pipeline doesn't stall
        pressure_hpa  = 1013.25
        temperature_c = 0.0
        humidity_pct  = 60.0
        wind_speed    = 0.0
        wind_dir      = 0.0
        cloud_cover   = 50.0
        weather_code  = 0
        coherence_pressure = 0.0
        coherence_thermal  = 0.0

    raw_payload = {
        "pressure_hpa":  pressure_hpa,
        "temperature_c": temperature_c,
        "humidity_pct":  humidity_pct,
        "wind_speed_kmh": wind_speed,
        "wind_dir_deg":  wind_dir,
        "cloud_cover_pct": cloud_cover,
        "weather_code":  weather_code,
    }

    # ------------------------------------------------------------------
    # Channel 1: helix_projection — barometric pressure vs semi-diurnal
    #
    # phase_external = where we are in the semi-diurnal (12h) cycle now
    # phase_field    = normalized pressure (high pressure → 1.0)
    # coherence      = data quality (0.85 live, 0.0 stub)
    # ------------------------------------------------------------------
    phase_field_pressure = _clamp((pressure_hpa - _P_LOW) / _P_SPAN)
    rec_pressure = _make_record(
        t=t_now,
        channel="helix_projection",
        phase_external=anchor.semi_diurnal_phase,
        phase_field=phase_field_pressure,
        coherence=coherence_pressure,
        raw=raw_payload,
        fetch_ok=fetch_ok,
    )

    # ------------------------------------------------------------------
    # Channel 2: thermal — temperature vs diurnal
    #
    # phase_external = where we are in the diurnal (24h) cycle now
    # phase_field    = normalized temperature
    # ------------------------------------------------------------------
    phase_field_thermal = _clamp((temperature_c - _T_LOW) / _T_SPAN)
    rec_thermal = _make_record(
        t=t_now,
        channel="thermal",
        phase_external=anchor.diurnal_phase,
        phase_field=phase_field_thermal,
        coherence=coherence_thermal,
        raw=raw_payload,
        fetch_ok=fetch_ok,
    )

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec_pressure, ensure_ascii=False) + "\n")
        f.write(json.dumps(rec_thermal, ensure_ascii=False) + "\n")

    status = "LIVE" if fetch_ok else "STUB (fetch failed)"
    print(f"OBSERVATORY [{status}]: wrote 2 natural records → {out_path}")
    print(f"  pressure  {pressure_hpa:.1f} hPa  phase_field={phase_field_pressure:.3f}  semi_diurnal_phase={anchor.semi_diurnal_phase:.3f}")
    print(f"  temp      {temperature_c:.1f}°C     phase_field={phase_field_thermal:.3f}  diurnal_phase={anchor.diurnal_phase:.3f}")


if __name__ == "__main__":
    main()
