#!/usr/bin/env python3
"""
PSR — MARKET DOMAIN (DAILY)

POSTURE:
- Read-only
- Deterministic
- One DomainWave per active channel (if both symbols present in raw)
- No inference beyond scalar transform
- Silent skip for missing channels

Reads raw market observations from:
  src/rhythm_os/data/dark_field/market_raw/YYYY-MM-DD.jsonl

Emits up to 6 DomainWaves covering:
  volatility_pressure, capital_cost, energy_pressure, maritime_pressure,
  food_cold_chain, infrastructure_materials
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rhythm_os.psr.domain_wave import DomainWave


RAW_DIR = Path("src/rhythm_os/data/dark_field/market_raw")
DOMAIN_DIR = Path("src/rhythm_os/data/dark_field/domain")


# ---------------------------------------------------------------------
# Channel definitions
# Each entry: (channel_name, phase_external_symbol, phase_field_symbol)
#   phase_external — primary pressure driver for this domain
#   phase_field    — reference / secondary signal
# ---------------------------------------------------------------------

CHANNELS: list[tuple[str, str, str]] = [
    ("volatility_pressure", "VIX", "SP500"),
    ("capital_cost", "TNX_10Y", "IRX_3M"),
    ("energy_pressure", "WTI_CRUDE", "NAT_GAS"),
    ("maritime_pressure", "BDRY", "ZIM"),
    ("food_cold_chain", "CORN", "LIVE_CATTLE"),
    ("infrastructure_materials", "COPPER", "STEEL_ETF"),
]


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

    return last


def main() -> None:
    raw = _read_latest_raw()
    if raw is None:
        return  # graceful degradation

    symbols: dict[str, float] = raw.get("symbols", {})
    today = _today()

    out = DOMAIN_DIR / f"{today}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    emitted = 0

    for channel, ext_key, field_key in CHANNELS:
        if ext_key not in symbols or field_key not in symbols:
            print(f"MARKET DOMAIN: {channel} — missing symbols, skipping")
            continue

        phase_external = symbols[ext_key]
        phase_field = symbols[field_key]
        phase_diff = phase_external - phase_field
        coherence = 1.0 / (1.0 + abs(phase_diff))

        wave = DomainWave(
            t=float(raw["t"]),
            domain="market",
            channel=channel,
            field_cycle="daily",
            phase_external=phase_external,
            phase_field=phase_field,
            phase_diff=phase_diff,
            coherence=coherence,
            extractor={
                "source": "psr.observe_market_daily",
                "raw_file": f"market_raw/{today}.jsonl",
                "channel": channel,
                "ext_symbol": ext_key,
                "field_symbol": field_key,
                "version": "v3",
            },
        )

        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(wave.to_dict(), separators=(",", ":")))
            f.write("\n")

        emitted += 1

    print(f"MARKET DOMAIN EMITTED | {emitted}/{len(CHANNELS)} channels")


if __name__ == "__main__":
    main()
