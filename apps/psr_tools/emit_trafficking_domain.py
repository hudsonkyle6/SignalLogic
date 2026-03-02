"""
Emit Human Trafficking Signal DomainWaves into the Dark Field.

COMMISSIONING SCRIPT — ONE WAY ONLY

Rules:
- append-only
- no transforms
- no filtering
- no interpretation

STATUS: STUB
    Awaiting data feed partnership (Thorn API / NCMEC or equivalent).
    Data feed must populate:
        src/rhythm_os/data/dark_field/human_trafficking/{YYYY-MM-DD}.jsonl
    before this emitter can run.

    Next step: Contact Thorn (thorn.org/partners) to establish feed access.
"""

from __future__ import annotations

from rhythm_os.psr.transform.trafficking_to_domain import (
    project_trafficking_domain,
)
from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.runtime.paths import DOMAIN_DIR
from datetime import datetime, timezone


def emit_trafficking_domain(
    *,
    window_days: int = 7,
) -> int:
    """
    Project trafficking signal domain data and append DomainWaves to Dark Field.

    Returns:
        int — number of waves emitted

    Raises:
        FileNotFoundError: if data feed has not been established.
    """
    waves = project_trafficking_domain(window_days=window_days)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bus_path = DOMAIN_DIR / f"{today}.jsonl"

    for wave in waves:
        append_domain_wave(bus_path, wave)

    return len(waves)


if __name__ == "__main__":
    # Raises FileNotFoundError until data feed is established.
    count = emit_trafficking_domain(window_days=7)
    print(f"TRAFFICKING DOMAIN EMITTED → {count} waves")
