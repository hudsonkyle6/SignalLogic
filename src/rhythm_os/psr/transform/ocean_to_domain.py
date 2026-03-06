"""
Ocean → Domain projection (PSR)

Reads ocean raw observations from the Ocean Raw dark field and projects them
into DomainWave records for the Natural domain.

POSTURE:
- Read-only
- No IO beyond reading dark field
- No persistence
- No thresholds
- No inference
- No observatory knowledge

Authority:
- PSR only
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.runtime.paths import OCEAN_RAW_DIR as DATA_DIR


# -------------------------------------------------------------------
# Dark field intake
# -------------------------------------------------------------------


def _latest_jsonl(dirpath: Path) -> Path:
    """
    Resolve the most recent dark field JSONL file for the Ocean Raw lane.

    Raises:
        FileNotFoundError if no ocean raw data exists.
    """
    files = sorted(dirpath.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"Ocean raw dark field missing: {dirpath}")
    return files[-1]


# -------------------------------------------------------------------
# Projection
# -------------------------------------------------------------------


def project_ocean_domain(*, window_days: int = 7) -> List[DomainWave]:
    """
    Project ocean raw observations into DomainWaves.

    Parameters:
        window_days: retained for interface consistency; not interpreted.

    Returns:
        List[DomainWave]

    Rules:
    - Pure projection only
    - No persistence
    - No filtering beyond lane identity
    - domain is always "natural" (ocean is a sub-source of the natural domain)
    """
    path = _latest_jsonl(DATA_DIR)
    waves: List[DomainWave] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            rec = json.loads(line)

            # Accept only ocean raw lane records
            if rec.get("lane") != "natural":
                continue

            data = rec.get("data", {})

            waves.append(
                DomainWave(
                    t=float(rec["t"]),
                    domain="natural",
                    channel=str(rec.get("channel", "wave_energy")),
                    field_cycle=str(rec.get("field_cycle", "semi_diurnal")),
                    phase_external=float(data["phase_external"]),
                    phase_field=float(data["phase_field"]),
                    phase_diff=float(data["phase_diff"]),
                    coherence=(
                        None
                        if data.get("coherence") is None
                        else float(data["coherence"])
                    ),
                    extractor={
                        "source": "psr.transform.ocean_to_domain",
                        "version": "v1",
                    },
                )
            )

    return waves
