from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from rhythm_os.psr.domain_wave import DomainWave


DOMAIN_DIR = Path("src/rhythm_os/data/dark_field/domain")


def _today_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DOMAIN_DIR / f"{today}.jsonl"


def read_today() -> List[DomainWave]:
    """
    Read today's DomainWave JSONL from the domain river.

    Rules:
    - Read-only
    - No directory creation
    - No inference
    """
    path = _today_path()
    if not path.exists():
        raise FileNotFoundError(f"Domain river file missing: {path}")

    waves: List[DomainWave] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            d = json.loads(line)

            waves.append(
                DomainWave(
                    t=float(d["t"]),
                    domain=str(d["domain"]),
                    channel=str(d["channel"]),
                    field_cycle=str(d["field_cycle"]),
                    phase_external=float(d["phase_external"]),
                    phase_field=float(d["phase_field"]),
                    phase_diff=float(d["phase_diff"]),
                    coherence=(
                        None if d.get("coherence") is None else float(d["coherence"])
                    ),
                    extractor=dict(d.get("extractor", {})),
                )
            )

    return waves
