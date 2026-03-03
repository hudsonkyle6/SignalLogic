"""
Emit Natural Lane DomainWaves into the CAN Bus (Dark Field)

COMMISSIONING SCRIPT — ONE WAY ONLY

Rules:
- append-only
- no transforms
- no filtering
- no interpretation
"""

from __future__ import annotations

from rhythm_os.psr.transform.natural_to_domain import (
    project_natural_domain,
)

from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.runtime.paths import DOMAIN_DIR
from signal_core.core.log import configure
from datetime import datetime, timezone


def emit_natural_domain(
    *,
    window_days: int = 7,
) -> int:
    """
    Project natural domain data and append DomainWaves to Dark Field.

    Returns:
        int — number of waves emitted
    """
    waves = project_natural_domain(window_days=window_days)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bus_path = DOMAIN_DIR / f"{today}.jsonl"

    for wave in waves:
        append_domain_wave(bus_path, wave)

    return len(waves)


if __name__ == "__main__":
    configure()
    emit_natural_domain(window_days=7)
