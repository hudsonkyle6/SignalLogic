from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.runtime.paths import DOMAIN_DIR
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)


def _bus_path_today() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DOMAIN_DIR / f"{today}.jsonl"


def main(*, window_days: int = 7) -> int:
    # Explicit bootstrap required by doctrine
    if not DOMAIN_DIR.exists():
        raise FileNotFoundError(f"Domain river missing: {DOMAIN_DIR}")

    bus_path = _bus_path_today()
    total = 0

    # Natural
    try:
        from rhythm_os.psr.transform.natural_to_domain import project_natural_domain

        waves = project_natural_domain(window_days=window_days)
        for w in waves:
            append_domain_wave(bus_path, w)
        total += len(waves)
        log.info("PSR: natural emitted %d waves", len(waves))
    except Exception as e:
        log.warning("PSR: natural skipped: %s", e)

    # Market (optional; only if you have it promoted similarly)
    try:
        from rhythm_os.psr.transform.market_to_domain import project_market_domain

        waves = project_market_domain(window_days=window_days)
        for w in waves:
            append_domain_wave(bus_path, w)
        total += len(waves)
        log.info("PSR: market emitted %d waves", len(waves))
    except Exception as e:
        log.warning("PSR: market skipped: %s", e)

    log.info("PSR: total emitted %d waves path=%s", total, bus_path)
    return total


if __name__ == "__main__":
    configure()
    main(window_days=7)
