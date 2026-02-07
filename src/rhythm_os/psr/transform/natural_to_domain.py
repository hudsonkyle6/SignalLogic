"""
Natural → Domain projection (PSR)

Reads RAW Natural observations from the Dark Field and projects them
into DomainWave records.

POSTURE:
- Read-only
- No IO beyond reading Dark Field
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


# ---------------------------------------------------------------------
# Dark Field intake
# ---------------------------------------------------------------------

DATA_DIR = Path("src/rhythm_os/data/dark_field/natural")


def _latest_jsonl(dirpath: Path) -> Path:
    """
    Resolve the most recent Dark Field JSONL file for the Natural lane.

    Raises:
        FileNotFoundError if no Natural Dark Field data exists.
    """
    files = sorted(dirpath.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"Natural dark field missing: {dirpath}")
    return files[-1]


# ---------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------

def project_natural_domain(*, window_days: int = 7) -> List[DomainWave]:
    """
    Project Natural RAW observations into DomainWaves.

    Parameters:
        window_days: retained for interface consistency; not interpreted.

    Returns:
        List[DomainWave]

    Rules:
    - Pure projection only
    - No persistence
    - No filtering beyond lane identity
    """

    path = _latest_jsonl(DATA_DIR)
    waves: List[DomainWave] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            rec = json.loads(line)

            # Accept only Natural RAW lane records
            if rec.get("lane") != "natural":
                continue

            data = rec.get("data", {})

            waves.append(
                DomainWave(
                    t=float(rec["t"]),
                    domain="natural",
                    channel=str(rec.get("channel", "helix_projection")),
                    field_cycle=str(rec.get("field_cycle", "computed")),
                    phase_external=float(data["phase_external"]),
                    phase_field=float(data["phase_field"]),
                    phase_diff=float(data["phase_diff"]),
                    coherence=(
                        None if data.get("coherence") is None
                        else float(data["coherence"])
                    ),
                    extractor={
                        "source": "psr.transform.natural_to_domain",
                        "version": "v1",
                    },
                )
            )

    return waves
