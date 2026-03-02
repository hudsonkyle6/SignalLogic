from __future__ import annotations

from typing import Optional, Iterable
from rhythm_os.psr.domain_wave import DomainWave


def latest_wave(
    waves: Iterable[DomainWave],
    *,
    domain: str,
    channel: str | None = None,
    field_cycle: str | None = None,
) -> Optional[DomainWave]:
    best = None
    for w in waves:
        if w.domain != domain:
            continue
        if channel is not None and w.channel != channel:
            continue
        if field_cycle is not None and w.field_cycle != field_cycle:
            continue
        if best is None or w.t > best.t:
            best = w
    return best
