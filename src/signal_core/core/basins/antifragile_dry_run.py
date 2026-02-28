#C:\Users\SignalADmin\Signal Archive\SignalLogic\src\signal_core\core\basins\antifragile_dry_run.py
"""
ANTIFRAGILE DRY RUN — HYDRO BASINS (READ-ONLY)

Purpose:
    • Instantiate the Hydro Basin layer in compute-only mode
    • Read meter telemetry from Dark Field
    • Map lanes → pressure scalars
    • Run antifragile + oracle math WITHOUT emission
    • Print human-readable basin summary

DOCTRINAL GUARANTEES:
    • No writes to Dark Field
    • No gates
    • No thresholds
    • No actuation
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
from statistics import mean

try:
    import pandas as pd
except ImportError as _e:
    raise ImportError(
        "pandas is required for antifragile dry-run analytics. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e

# ---- Canonical antifragile math ----
from rhythm_os.domain.antifragile.drift import compute_drift_index
from rhythm_os.domain.antifragile.state import compute_antifragile_state

# ---- Canonical memory / afterglow physics ----
from rhythm_os.core.memory.afterglow import compute_memory_fields

# ---- Canonical oracle (DESCRIPTIVE ONLY) ----




# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

DARK_FIELD_METERS = Path("src/rhythm_os/data/dark_field/meters")
MAX_FILES = 2        # last N daily files (adjust freely)
MIN_POINTS = 10


# ---------------------------------------------------------------------
# PRESSURE MAPPING (EXPLICIT, REVERSIBLE)
# ---------------------------------------------------------------------

def pressure_scalar(lane: str, channel: str, data: dict) -> float | None:
    if lane == "cpu" and channel == "cpu:util":
        return data.get("cpu_percent_mean")

    if lane == "cpu" and channel == "cpu:freq":
        return data.get("cur_norm_0_1") or data.get("cur_mhz_mean")

    if lane == "proc":
        return data.get("cpu_rate_core_equiv")

    if lane == "net":
        return data.get("in_rate_bps", 0.0) + data.get("out_rate_bps", 0.0)

    return None


# ---------------------------------------------------------------------
# LOAD METER WAVES (READ-ONLY)
# ---------------------------------------------------------------------

def load_meter_series() -> dict:
    series = defaultdict(list)

    files = sorted(DARK_FIELD_METERS.glob("*.jsonl"))[-MAX_FILES:]

    for f in files:
        for line in f.read_text().splitlines():
            pkt = json.loads(line)

            lane = pkt["lane"]
            channel = pkt["channel"]
            t = pkt["t"]
            data = pkt["data"]

            p = pressure_scalar(lane, channel, data)
            if p is None:
                continue

            series[(lane, channel)].append((t, p))

    return series


# ---------------------------------------------------------------------
# MAIN DRY RUN
# ---------------------------------------------------------------------

def main() -> None:
    print("\n=== ANTIFRAGILE DRY RUN — HYDRO BASINS ===\n")

    series = load_meter_series()

    basin_states = {}

    for (lane, channel), pts in series.items():
        if len(pts) < MIN_POINTS:
            continue

        values = [v for _, v in pts]
        timestamps = [t for t, _ in pts]

        df_mem = pd.DataFrame({
            "Date": pd.to_datetime(timestamps, unit="s"),
            "HSTResDrift": values,        # proxy is OK for dry run
            "Amplitude": values,          # same proxy
            "ResonanceValue": values,     # same proxy
        })

        df_mem = compute_memory_fields(df_mem)

        

        baseline_value = (sum(values) / len(values)) if values else 0.0
        baseline = [baseline_value] * len(values)
        drift = compute_drift_index(values, baseline)
        
        afterglow_series = df_mem["Afterglow"]
        memory_charge = df_mem["MemoryCharge"]

        half_life = (
            df_mem["Date"]
            .iloc[-1] - df_mem["Date"][afterglow_series < 0.5].iloc[-1]
        ).total_seconds() if (afterglow_series < 0.5).any() else None

        persistence = int((afterglow_series > 0.1).sum())


        basin_states[(lane, channel)] = {
            "peak": max(values),
            "mean": mean(values),
            "drift": drift,
            
            
            "afterglow_mean": float(afterglow_series.mean()),
            "half_life_s": half_life,
            "persistence": persistence,
        }


        print(f"{lane}:{channel}")
        print(f"  peak        : {max(values):.3f}")
        print(f"  mean        : {mean(values):.3f}")
        print(f"  drift       : {drift:.3f}")
        
        print(f"  afterglow   : {afterglow_series.mean():.3f}")
        print(f"  half-life   : {half_life if half_life is not None else 'None'}")
        print(f"  persistence : {persistence}\n")

        

    # -----------------------------------------------------------------
    # ORACLE ALIGNMENT (DESCRIPTIVE ONLY)
    # -----------------------------------------------------------------



    print("\n=== DRY RUN COMPLETE — NO ACTION TAKEN ===\n")


if __name__ == "__main__":
    main()
