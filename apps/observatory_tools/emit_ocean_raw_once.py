"""
Ocean Observatory — Buoy Telemetry Ingress

Ingests offshore buoy data from either:
  (a) CUMULUS live API  (default)
  (b) local CSV file   (--csv, for testing / backfill)

Computes derived physical signals, aggregates to hourly cadence, and
writes raw phase records to the Ocean Raw dark field.

No raw telemetry enters the engine.  Only derived physics signals are emitted.

Pipeline:
    CUMULUS API / CSV → normalize → compute_derived_signals
                      → resample_to_hourly → emit_ocean_raw → OCEAN_RAW_DIR

Live API usage:
    export CUMULUS_API_TOKEN="90|..."
    python emit_ocean_raw_once.py --spotter-id SPOT-32724C

CSV usage (testing / backfill):
    python emit_ocean_raw_once.py --csv /path/to/buoy.csv

CUMULUS API field mapping (actual response fields → internal names):
    waveSignHeight  → waveSignificantHeight
    windDirection   → windDirection  (int in API, coerced to float)
    surfaceTemp     → surfaceTemp    (may be null → defaults to 15.0°C)
    barometerData   → barometerData  (string in API, coerced to float)

Authority: observatory only — no inference, no dispatch, no thresholds.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from rhythm_os.runtime.paths import OCEAN_RAW_DIR as OUT_DIR
from rhythm_os.runtime.temporal_anchor import compute_anchor, SEMI_DIURNAL_PERIOD_S
from signal_core.core.log import configure, get_logger
from signal_core.domains.natural.derived_ocean_signals import (
    wave_energy,
    normalize_wave_energy,
    normalize_wave_period,
    wind_vector,
    normalize_wind_component,
    normalize_pressure_gradient,
    normalize_surface_temp,
)

log = get_logger(__name__)

# -------------------------------------------------------------------
# CUMULUS API constants
# -------------------------------------------------------------------

_CUMULUS_BASE_URL = "https://cumulus.coastalmeasures.com"
_CUMULUS_SPOTTER_PATH = "/api/sensors/spotter/{spotter_id}"
_DEFAULT_SPOTTER_ID = "SPOT-32724C"
_DEFAULT_LOOKBACK_HOURS = 25  # slightly more than 24h to avoid boundary gaps

# Request limit: 4 obs/hour × 25h × 2× headroom = 200.
# If the API returns exactly this many, we may have been truncated.
_FETCH_LIMIT = 200

# Default surface temp when buoy doesn't report it (°C)
_SURFACE_TEMP_DEFAULT = 15.0

# -------------------------------------------------------------------
# Aggregation rules per channel (applied over the hourly window)
# -------------------------------------------------------------------

_RESAMPLE_RULE = "1h"

_AGG_MAP: Dict[str, str] = {
    "wave_energy_J_m2": "mean",
    "wave_period_s": "mean",
    "wind_vx_m_s": "mean",
    "wind_vy_m_s": "mean",
    "pressure_gradient_hpa": "sum",
    "surface_temp_c": "mean",
}

# Channel → (field_cycle, window_s) metadata
_CHANNEL_META: Dict[str, tuple] = {
    "wave_energy": ("semi_diurnal", SEMI_DIURNAL_PERIOD_S),
    "wave_period": ("semi_diurnal", SEMI_DIURNAL_PERIOD_S),
    "wind_vector_x": ("diurnal", 86400.0),
    "wind_vector_y": ("diurnal", 86400.0),
    "pressure_gradient": ("semi_diurnal", SEMI_DIURNAL_PERIOD_S),
    "surface_temp": ("diurnal", 86400.0),
}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _circular_diff(a: float, b: float) -> float:
    """Signed shortest arc from b to a in [0, 1] phase space. Result in [-0.5, 0.5]."""
    d = (a - b) % 1.0
    return d - 1.0 if d > 0.5 else d


def _make_record(
    t: float,
    channel: str,
    phase_external: float,
    phase_field: float,
    coherence: float,
    raw: Dict[str, Any],
    source: str = "cumulus_api",
) -> Dict[str, Any]:
    phase_diff = _circular_diff(phase_external, phase_field)
    field_cycle, window_s = _CHANNEL_META[channel]
    return {
        "t": t,
        "domain": "ocean_raw",
        "lane": "natural",
        "channel": channel,
        "field_cycle": field_cycle,
        "window_s": window_s,
        "data": {
            "phase_external": phase_external,
            "phase_field": phase_field,
            "phase_diff": phase_diff,
            "coherence": coherence,
        },
        "raw": raw,
        "extractor": {
            "source": source,
            "runner": "emit_ocean_raw_once",
            "version": "v2",
        },
    }


# -------------------------------------------------------------------
# CUMULUS live API fetch
# -------------------------------------------------------------------


def fetch_cumulus_data(
    spotter_id: str,
    api_token: str,
    *,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch spotter telemetry from the CUMULUS API.

    Args:
        spotter_id: e.g. "SPOT-32724C"
        api_token:  Bearer token string
        start_dt:   UTC datetime lower bound (inclusive); defaults to 25h ago
        end_dt:     UTC datetime upper bound (inclusive); defaults to now

    Returns:
        List of raw observation dicts from data[].

    Raises:
        RuntimeError: on non-2xx HTTP response
    """
    now = datetime.now(timezone.utc)
    if end_dt is None:
        end_dt = now
    if start_dt is None:
        start_dt = now - timedelta(hours=_DEFAULT_LOOKBACK_HOURS)

    url = _CUMULUS_BASE_URL + _CUMULUS_SPOTTER_PATH.format(spotter_id=spotter_id)
    headers = {"Authorization": f"Bearer {api_token}"}
    params = {
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "limit": _FETCH_LIMIT,
    }

    log.info(
        "OCEAN OBSERVATORY: fetching spotter=%s start=%s end=%s limit=%d",
        spotter_id,
        params["start_date"],
        params["end_date"],
        _FETCH_LIMIT,
    )

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"CUMULUS API request failed: {exc.response.status_code} {exc.response.text[:200]}"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"CUMULUS API network error: {exc}") from exc

    payload = resp.json()
    records: List[Dict[str, Any]] = payload.get("data", [])

    if len(records) >= _FETCH_LIMIT:
        log.warning(
            "OCEAN OBSERVATORY: response hit limit=%d — some records may be missing. "
            "Increase _FETCH_LIMIT or narrow the lookback window. spotter=%s",
            _FETCH_LIMIT,
            spotter_id,
        )

    # Client-side date filter as fallback if the API ignores the params
    filtered = []
    for rec in records:
        ts_str = rec.get("timestamp", "")
        if not ts_str:
            continue
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if start_dt <= ts <= end_dt:
            filtered.append(rec)

    log.info(
        "OCEAN OBSERVATORY: received %d records, %d in window spotter=%s",
        len(records),
        len(filtered),
        spotter_id,
    )
    return filtered


def normalize_cumulus_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw CUMULUS API records into a normalized DataFrame.

    Handles:
    - Field rename: waveSignHeight → waveSignificantHeight
    - Type coercion: string numerics → float (barometerData, waveSignHeight, etc.)
    - windDirection: int in API → float
    - surfaceTemp: null → _SURFACE_TEMP_DEFAULT
    - timestamp: string → UTC DatetimeIndex

    Args:
        records: list of dicts from the CUMULUS data[] array

    Returns:
        DataFrame sorted ascending by UTC timestamp with DatetimeIndex.
    """
    if not records:
        raise ValueError("No records returned from CUMULUS API")

    df = pd.DataFrame(records)

    # Parse and set timestamp as UTC index
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")

    # Rename waveSignHeight → waveSignificantHeight for pipeline consistency
    if "waveSignHeight" in df.columns:
        df = df.rename(columns={"waveSignHeight": "waveSignificantHeight"})

    # Coerce string numerics to float
    for col in ("waveSignificantHeight", "wavePeakPeriod", "waveMeanPeriod",
                "windSpeed", "barometerData", "humidity",
                "batteryVoltage", "solarVoltage"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # windDirection is int in the API — coerce to float explicitly
    if "windDirection" in df.columns:
        df["windDirection"] = pd.to_numeric(df["windDirection"], errors="coerce").astype(float)

    # surfaceTemp: null → default
    if "surfaceTemp" in df.columns:
        df["surfaceTemp"] = pd.to_numeric(df["surfaceTemp"], errors="coerce").fillna(
            _SURFACE_TEMP_DEFAULT
        )

    return df


# -------------------------------------------------------------------
# CSV data loading (testing / backfill)
# -------------------------------------------------------------------


def load_buoy_data(path: Path) -> pd.DataFrame:
    """
    Load and sort buoy CSV.

    Expected columns (subset used; others ignored):
        timestamp               ISO-8601 or parseable datetime
        waveSignificantHeight   metres
        wavePeakPeriod          seconds
        windSpeed               m/s
        windDirection           degrees (meteorological, FROM bearing)
        barometerData           hPa
        surfaceTemp             °C

    Returns:
        DataFrame sorted ascending by timestamp with UTC DatetimeIndex.
    """
    if not path.exists():
        raise FileNotFoundError(f"Buoy CSV not found: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"])

    if "timestamp" not in df.columns:
        raise ValueError("Buoy CSV missing 'timestamp' column")

    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")
    df.index = (
        pd.DatetimeIndex(df.index).tz_localize("UTC")
        if df.index.tz is None
        else df.index.tz_convert("UTC")
    )
    return df


# -------------------------------------------------------------------
# Shared derivation pipeline
# -------------------------------------------------------------------


def compute_derived_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute derived physics signals from raw buoy telemetry.

    Accepts either waveSignificantHeight (CSV convention) or
    waveSignHeight (CUMULUS API) — both are handled.

    Adds columns:
        wave_energy_J_m2      wave energy density (J/m²)
        wind_vx_m_s           eastward wind component (m/s)
        wind_vy_m_s           northward wind component (m/s)
        pressure_gradient_hpa barometric pressure diff vs previous row (hPa)
        wave_period_s         peak wave period (seconds)
        surface_temp_c        sea surface temperature (°C)
    """
    df = df.copy()

    # Defaults for missing columns
    if "waveSignificantHeight" not in df.columns:
        df["waveSignificantHeight"] = 0.0
    if "wavePeakPeriod" not in df.columns:
        df["wavePeakPeriod"] = 10.0
    if "windSpeed" not in df.columns:
        df["windSpeed"] = 0.0
    if "windDirection" not in df.columns:
        df["windDirection"] = 0.0
    if "barometerData" not in df.columns:
        df["barometerData"] = 1013.25
    if "surfaceTemp" not in df.columns:
        df["surfaceTemp"] = _SURFACE_TEMP_DEFAULT

    df["wave_energy_J_m2"] = df["waveSignificantHeight"].apply(
        lambda h: wave_energy(float(h))
    )

    vx_vy = df.apply(
        lambda row: wind_vector(float(row["windSpeed"]), float(row["windDirection"])),
        axis=1,
    )
    df["wind_vx_m_s"] = vx_vy.apply(lambda t: t[0])
    df["wind_vy_m_s"] = vx_vy.apply(lambda t: t[1])

    df["pressure_gradient_hpa"] = (
        pd.to_numeric(df["barometerData"], errors="coerce").diff().fillna(0.0)
    )

    df["wave_period_s"] = pd.to_numeric(df["wavePeakPeriod"], errors="coerce").fillna(10.0)
    df["surface_temp_c"] = pd.to_numeric(df["surfaceTemp"], errors="coerce").fillna(
        _SURFACE_TEMP_DEFAULT
    )

    return df


def resample_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 15-minute buoy cadence to hourly engine window.

    Aggregation rules (per spec):
        wave_energy       → mean
        wave_period       → mean
        wind_vector       → mean
        pressure_gradient → sum
        surface_temp      → mean
    """
    cols = [c for c in _AGG_MAP if c in df.columns]
    agg = {c: _AGG_MAP[c] for c in cols}
    hourly = df[cols].resample(_RESAMPLE_RULE).agg(agg)
    hourly = hourly.dropna(how="all")
    return hourly


# -------------------------------------------------------------------
# Emission
# -------------------------------------------------------------------


def emit_ocean_raw(hourly: pd.DataFrame, out_path: Path, *, source: str = "cumulus_api") -> int:
    """
    Emit hourly buoy-derived records as ocean raw phase records.

    Args:
        hourly:   hourly-resampled DataFrame with derived columns
        out_path: JSONL file to append records to
        source:   extractor source label ("cumulus_api" or "buoy_csv")

    Returns:
        Number of records written.
    """
    count = 0

    for ts, row in hourly.iterrows():
        t = ts.timestamp()
        anchor = compute_anchor(t, domain="natural")

        raw_snapshot: Dict[str, Any] = {}
        for col in _AGG_MAP:
            if col in row.index:
                raw_snapshot[col] = round(float(row[col]), 6)

        e_raw = float(row.get("wave_energy_J_m2", 0.0))
        records = [
            _make_record(
                t=t,
                channel="wave_energy",
                phase_external=anchor.semi_diurnal_phase,
                phase_field=normalize_wave_energy(e_raw),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
            _make_record(
                t=t,
                channel="wave_period",
                phase_external=anchor.semi_diurnal_phase,
                phase_field=normalize_wave_period(float(row.get("wave_period_s", 10.0))),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
            _make_record(
                t=t,
                channel="wind_vector_x",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_wind_component(float(row.get("wind_vx_m_s", 0.0))),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
            _make_record(
                t=t,
                channel="wind_vector_y",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_wind_component(float(row.get("wind_vy_m_s", 0.0))),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
            _make_record(
                t=t,
                channel="pressure_gradient",
                phase_external=anchor.semi_diurnal_phase,
                phase_field=normalize_pressure_gradient(
                    float(row.get("pressure_gradient_hpa", 0.0))
                ),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
            _make_record(
                t=t,
                channel="surface_temp",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_surface_temp(
                    float(row.get("surface_temp_c", _SURFACE_TEMP_DEFAULT))
                ),
                coherence=0.85,
                raw=raw_snapshot,
                source=source,
            ),
        ]

        with out_path.open("a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        count += len(records)

    return count


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main(
    *,
    spotter_id: str = _DEFAULT_SPOTTER_ID,
    api_token: Optional[str] = None,
    buoy_csv: Optional[Path] = None,
    lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.jsonl"

    if buoy_csv is not None:
        # CSV mode — for testing or historical backfill
        log.info("OCEAN OBSERVATORY: CSV mode path=%s", buoy_csv)
        df = load_buoy_data(buoy_csv)
        source = "buoy_csv"
    else:
        # Live API mode
        token = api_token or os.environ.get("CUMULUS_API_TOKEN", "")
        if not token:
            log.error(
                "OCEAN OBSERVATORY: no API token — set CUMULUS_API_TOKEN or pass --api-token"
            )
            return

        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=lookback_hours)
        records = fetch_cumulus_data(
            spotter_id, token, start_dt=start_dt, end_dt=now
        )
        if not records:
            log.warning(
                "OCEAN OBSERVATORY: no records returned for spotter=%s window=%dh",
                spotter_id,
                lookback_hours,
            )
            return

        df = normalize_cumulus_df(records)
        source = "cumulus_api"

    df = compute_derived_signals(df)
    hourly = resample_to_hourly(df)

    n = emit_ocean_raw(hourly, out_path, source=source)
    log.info(
        "OCEAN OBSERVATORY [%s]: wrote %d records path=%s hours=%d spotter=%s",
        source.upper(),
        n,
        out_path,
        len(hourly),
        spotter_id,
    )


if __name__ == "__main__":
    import argparse

    configure()

    parser = argparse.ArgumentParser(
        description="Ingest Plum Island buoy telemetry into ocean raw dark field"
    )
    parser.add_argument(
        "--spotter-id",
        default=_DEFAULT_SPOTTER_ID,
        help=f"CUMULUS spotter ID (default: {_DEFAULT_SPOTTER_ID})",
    )
    parser.add_argument(
        "--api-token",
        default=None,
        help="CUMULUS Bearer token (default: $CUMULUS_API_TOKEN env var)",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=_DEFAULT_LOOKBACK_HOURS,
        help=f"Hours of history to fetch (default: {_DEFAULT_LOOKBACK_HOURS})",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Load from local CSV instead of live API (for testing / backfill)",
    )
    args = parser.parse_args()

    main(
        spotter_id=args.spotter_id,
        api_token=args.api_token,
        buoy_csv=args.csv,
        lookback_hours=args.lookback_hours,
    )
