"""
Ocean Observatory — Buoy Telemetry Ingress

Loads offshore buoy data from a CSV file, computes derived physical signals,
aggregates to hourly cadence (matching the engine window), and writes raw
phase records to the Ocean Raw dark field.

No raw telemetry enters the engine.  Only derived physics signals are emitted.

Pipeline position:
    Buoy CSV → load_buoy_data → compute_derived_signals
             → resample_to_hourly → emit raw phase records → OCEAN_RAW_DIR

Expected CSV columns (subset used; others ignored):
    timestamp               ISO-8601 or parseable datetime
    waveSignificantHeight   metres
    wavePeakPeriod          seconds
    windSpeed               m/s
    windDirection           degrees (meteorological, FROM bearing)
    barometerData           hPa
    surfaceTemp             °C

Authority: observatory only — no inference, no dispatch, no thresholds.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

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
            "source": "buoy_csv",
            "runner": "emit_ocean_raw_once",
            "version": "v1",
        },
    }


# -------------------------------------------------------------------
# Data loading and derivation
# -------------------------------------------------------------------


def load_buoy_data(path: Path) -> pd.DataFrame:
    """
    Load and sort buoy CSV.

    Args:
        path: path to buoy CSV file

    Returns:
        DataFrame sorted ascending by timestamp with DatetimeIndex.

    Raises:
        FileNotFoundError: if path does not exist
        ValueError: if 'timestamp' column is missing
    """
    if not path.exists():
        raise FileNotFoundError(f"Buoy CSV not found: {path}")

    df = pd.read_csv(path, parse_dates=["timestamp"])

    if "timestamp" not in df.columns:
        raise ValueError("Buoy CSV missing 'timestamp' column")

    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    return df


def compute_derived_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute derived physics signals from raw buoy telemetry.

    Adds columns:
        wave_energy_J_m2      wave energy density (J/m²)
        wind_vx_m_s           eastward wind component (m/s)
        wind_vy_m_s           northward wind component (m/s)
        pressure_gradient_hpa barometric pressure diff vs previous row (hPa)

    Source columns consumed (filled with defaults when absent):
        waveSignificantHeight, wavePeakPeriod, windSpeed,
        windDirection, barometerData, surfaceTemp
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
        df["surfaceTemp"] = 15.0

    df["wave_energy_J_m2"] = df["waveSignificantHeight"].apply(
        lambda h: wave_energy(float(h))
    )

    vx_vy = df.apply(
        lambda row: wind_vector(float(row["windSpeed"]), float(row["windDirection"])),
        axis=1,
    )
    df["wind_vx_m_s"] = vx_vy.apply(lambda t: t[0])
    df["wind_vy_m_s"] = vx_vy.apply(lambda t: t[1])

    df["pressure_gradient_hpa"] = df["barometerData"].diff().fillna(0.0)

    # Rename for aggregation consistency
    df["wave_period_s"] = df["wavePeakPeriod"].astype(float)
    df["surface_temp_c"] = df["surfaceTemp"].astype(float)

    return df


def resample_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 15-minute buoy cadence to hourly engine window.

    Aggregation rules (per spec):
        wave_energy      → mean
        wave_period      → mean
        wind_vector      → mean
        pressure_gradient → sum
        surface_temp     → mean
    """
    cols = [c for c in _AGG_MAP if c in df.columns]
    agg = {c: _AGG_MAP[c] for c in cols}
    hourly = df[cols].resample(_RESAMPLE_RULE).agg(agg)
    hourly = hourly.dropna(how="all")
    return hourly


# -------------------------------------------------------------------
# Emission
# -------------------------------------------------------------------


def emit_ocean_raw(hourly: pd.DataFrame, out_path: Path) -> int:
    """
    Emit hourly buoy-derived records as ocean raw phase records.

    Args:
        hourly:   hourly-resampled DataFrame with derived columns
        out_path: JSONL file to append records to

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

        # wave_energy
        e_raw = float(row.get("wave_energy_J_m2", 0.0))
        records = [
            _make_record(
                t=t,
                channel="wave_energy",
                phase_external=anchor.semi_diurnal_phase,
                phase_field=normalize_wave_energy(e_raw),
                coherence=0.85,
                raw=raw_snapshot,
            ),
            _make_record(
                t=t,
                channel="wave_period",
                phase_external=anchor.semi_diurnal_phase,
                phase_field=normalize_wave_period(float(row.get("wave_period_s", 10.0))),
                coherence=0.85,
                raw=raw_snapshot,
            ),
            _make_record(
                t=t,
                channel="wind_vector_x",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_wind_component(float(row.get("wind_vx_m_s", 0.0))),
                coherence=0.85,
                raw=raw_snapshot,
            ),
            _make_record(
                t=t,
                channel="wind_vector_y",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_wind_component(float(row.get("wind_vy_m_s", 0.0))),
                coherence=0.85,
                raw=raw_snapshot,
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
            ),
            _make_record(
                t=t,
                channel="surface_temp",
                phase_external=anchor.diurnal_phase,
                phase_field=normalize_surface_temp(
                    float(row.get("surface_temp_c", 15.0))
                ),
                coherence=0.85,
                raw=raw_snapshot,
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


def main(buoy_csv: Optional[Path] = None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if buoy_csv is None:
        log.warning(
            "OCEAN OBSERVATORY: no buoy CSV supplied — pass --csv <path> to ingest data"
        )
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.jsonl"

    log.info("OCEAN OBSERVATORY: loading buoy data path=%s", buoy_csv)
    df = load_buoy_data(buoy_csv)
    df = compute_derived_signals(df)
    hourly = resample_to_hourly(df)

    n = emit_ocean_raw(hourly, out_path)
    log.info(
        "OCEAN OBSERVATORY: wrote %d ocean raw records path=%s hours=%d",
        n,
        out_path,
        len(hourly),
    )


if __name__ == "__main__":
    import argparse

    configure()

    parser = argparse.ArgumentParser(description="Ingest buoy CSV into ocean raw dark field")
    parser.add_argument("--csv", type=Path, default=None, help="Path to buoy CSV file")
    args = parser.parse_args()

    main(buoy_csv=args.csv)
