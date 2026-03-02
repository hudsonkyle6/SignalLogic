"""
Human Trafficking Signal → Domain projection (PSR)

Reads RAW trafficking signal observations from the Dark Field and projects
them into DomainWave records.

POSTURE:
- Read-only
- No IO beyond reading Dark Field
- No persistence
- No thresholds
- No inference
- No observatory knowledge

Authority:
- PSR only

STATUS: STUB
    Awaiting data feed partnership (Thorn API / NCMEC or equivalent).
    Integration point is _latest_jsonl() and the record schema below.

Expected record schema (feed-specific, to be confirmed with data partner):
    {
        "t": <float UTC timestamp>,
        "lane": "human_trafficking",
        "channel": <str, feed-defined channel name>,
        "field_cycle": <str, "diurnal" | "semi_diurnal" | "seasonal" | "longwave">,
        "data": {
            "phase_external": <float radians [0, 2π)>,
            "phase_field":    <float radians [0, 2π)>,
            "phase_diff":     <float radians [-π, π]>,
            "coherence":      <float [0, 1] or null>
        }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from rhythm_os.psr.domain_wave import DomainWave


# ---------------------------------------------------------------------
# Dark Field intake
# NOTE: Path will be overridden by feed-specific config once a data
# partnership (Thorn / NCMEC or equivalent) is established.
# ---------------------------------------------------------------------

DATA_DIR = Path("src/rhythm_os/data/dark_field/human_trafficking")


def _latest_jsonl(dirpath: Path) -> Path:
    """
    Resolve the most recent Dark Field JSONL file for the trafficking lane.

    Raises:
        FileNotFoundError if no Dark Field data exists for this domain.
    """
    files = sorted(dirpath.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(
            f"Human trafficking dark field missing: {dirpath}\n"
            "DATA FEED REQUIRED — contact Thorn (thorn.org/partners) "
            "or NCMEC to establish data pipeline before this transform can run."
        )
    return files[-1]


# ---------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------


def project_trafficking_domain(*, window_days: int = 7) -> List[DomainWave]:
    """
    Project human trafficking signal RAW observations into DomainWaves.

    Parameters:
        window_days: retained for interface consistency; not interpreted.

    Returns:
        List[DomainWave]

    Rules:
    - Pure projection only
    - No persistence
    - No filtering beyond lane identity
    - No semantic interpretation of signals

    Raises:
        FileNotFoundError: if data feed has not been established.
    """
    path = _latest_jsonl(DATA_DIR)
    waves: List[DomainWave] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            rec = json.loads(line)

            # Accept only human_trafficking lane records
            if rec.get("lane") != "human_trafficking":
                continue

            data = rec.get("data", {})

            waves.append(
                DomainWave(
                    t=float(rec["t"]),
                    domain="human_trafficking",
                    channel=str(rec.get("channel", "signal")),
                    field_cycle=str(rec.get("field_cycle", "diurnal")),
                    phase_external=float(data["phase_external"]),
                    phase_field=float(data["phase_field"]),
                    phase_diff=float(data["phase_diff"]),
                    coherence=(
                        None
                        if data.get("coherence") is None
                        else float(data["coherence"])
                    ),
                    extractor={
                        "source": "psr.transform.trafficking_to_domain",
                        "version": "v1",
                    },
                )
            )

    return waves
