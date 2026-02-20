#!/usr/bin/env python3
"""
PSR — MARKET DOMAIN (DAILY)

POSTURE:
- Read-only
- Deterministic
- One DomainWave per day (if raw exists)
- No inference beyond scalar transform
- Silent skip if no raw present

Reads raw market observations from:
  src/rhythm_os/data/dark_field/market_raw/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rhythm_os.psr.domain_wave import DomainWave


RAW_DIR = Path("src/rhythm_os/data/dark_field/market_raw")
DOMAIN_DIR = Path("src/rhythm_os/data/dark_field/domain")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_latest_raw() -> dict | None:
    path = RAW_DIR / f"{_today()}.jsonl"

    if not path.exists():
        print("MARKET DOMAIN: no raw file for today (skipping)")
        return None

    last = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = json.loads(line)

    if last is None:
        print("MARKET DOMAIN: raw file empty (skipping)")
        return None

    return last


def main() -> None:
    raw = _read_latest_raw()
    if raw is None:
        return  # graceful degradation

    try:
        vix = float(raw["symbols"]["VIX"])
        spx = float(raw["symbols"]["SP500"])
    except Exception:
        print("MARKET DOMAIN: malformed raw structure (skipping)")
        return

    # Pressure proxy (v1): VIX level
    phase_external = vix
    phase_field = spx
    phase_diff = phase_external - phase_field

    # Minimal bounded coherence proxy
    coherence = 1.0 / (1.0 + abs(phase_diff))

    wave = DomainWave(
        t=float(raw["t"]),
        domain="market",
        channel="volatility_pressure",
        field_cycle="daily",
        phase_external=phase_external,
        phase_field=phase_field,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor={
            "source": "psr.observe_market_daily",
            "raw_file": f"market_raw/{_today()}.jsonl",
            "version": "v2",
        },
    )

    out = DOMAIN_DIR / f"{_today()}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(wave.to_dict(), separators=(",", ":")))
        f.write("\n")

    print(
        f"MARKET DOMAIN EMITTED | "
        f"VIX={phase_external:.2f} "
        f"coherence={coherence:.4f}"
    )


if __name__ == "__main__":
    main()
