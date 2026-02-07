from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rhythm_os.psr.append_domain_wave import append_domain_wave

BUS_ROOT = Path("src/rhythm_os/data/dark_field")
DOMAIN_DIR = BUS_ROOT / "domain"


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
        print(f"PSR: natural -> {len(waves)} waves")
    except Exception as e:
        print(f"PSR: natural skipped ({e})")

    # Market (optional; only if you have it promoted similarly)
    try:
        from rhythm_os.psr.transform.market_to_domain import project_market_domain
        waves = project_market_domain(window_days=window_days)
        for w in waves:
            append_domain_wave(bus_path, w)
        total += len(waves)
        print(f"PSR: market -> {len(waves)} waves")
    except Exception as e:
        print(f"PSR: market skipped ({e})")

    print(f"PSR: total emitted -> {total} waves @ {bus_path}")
    return total


if __name__ == "__main__":
    main(window_days=7)
