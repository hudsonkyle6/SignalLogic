#!/usr/bin/env python3
"""
MARKET OBSERVATORY — RAW (ONE SHOT)

POSTURE:
- Observatory instrument
- Append-only
- No inference
- No aggregation
- No PSR logic
- No corrupted signal admitted

Emits one raw market observation per run covering 6 business domains:
  volatility, capital_cost, energy, maritime, food_cold_chain,
  infrastructure_materials

If a symbol is unavailable → excluded from record (not a hard failure).
If no symbols available at all → silent exit.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf


# ---------------------------------------------------------------------
# Root-safe path resolution (never relative to CWD)
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "src/rhythm_os/data/dark_field/market_raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# Ticker → friendly symbol name (used as record keys in dark field)
# Grouped by business domain for clarity.
# ---------------------------------------------------------------------

TICKER_NAMES: dict[str, str] = {
    # Volatility
    "^GSPC": "SP500",
    "^VIX": "VIX",
    # Capital Cost (yield curve + credit quality)
    "^TNX": "TNX_10Y",
    "^IRX": "IRX_3M",
    "HYG": "HYG",
    # Energy
    "CL=F": "WTI_CRUDE",
    "NG=F": "NAT_GAS",
    # Maritime
    "BDRY": "BDRY",
    "ZIM": "ZIM",
    "MATX": "MATX",
    # Food / Cold Chain
    "ZC=F": "CORN",
    "ZW=F": "WHEAT",
    "ZS=F": "SOYBEANS",
    "LE=F": "LIVE_CATTLE",
    # Infrastructure Materials
    "HG=F": "COPPER",
    "SLX": "STEEL_ETF",
    "WOOD": "LUMBER_ETF",
}

# Minimum symbol pairs required for each domain channel
_DOMAIN_PAIRS: dict[str, tuple[str, str]] = {
    "volatility": ("SP500", "VIX"),
    "capital_cost": ("TNX_10Y", "IRX_3M"),
    "energy": ("WTI_CRUDE", "NAT_GAS"),
    "maritime": ("BDRY", "ZIM"),
    "food": ("CORN", "LIVE_CATTLE"),
    "materials": ("COPPER", "STEEL_ETF"),
}


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    now = datetime.now(timezone.utc)
    tickers = list(TICKER_NAMES.keys())

    data = yf.download(
        tickers,
        period="2d",
        interval="1d",
        progress=False,
        auto_adjust=False,  # explicit to avoid future behavior drift
    )

    if data.empty:
        print("MARKET RAW: no data returned")
        sys.exit(0)

    # -----------------------------------------------------------------
    # Extract close prices — skip unavailable or NaN tickers gracefully
    # -----------------------------------------------------------------

    symbols: dict[str, float] = {}
    for ticker, name in TICKER_NAMES.items():
        try:
            val = float(data["Close"][ticker].iloc[-1])
            if val == val:  # NaN guard
                symbols[name] = val
        except (KeyError, IndexError, TypeError):
            pass  # ticker temporarily unavailable — not a hard failure

    if not symbols:
        print("MARKET RAW: no valid symbols available")
        sys.exit(0)

    # -----------------------------------------------------------------
    # Construct record
    # -----------------------------------------------------------------

    record = {
        "t": now.timestamp(),
        "domain": "market_raw",
        "lane": "market",
        "symbols": symbols,
        "extractor": {
            "source": "yfinance",
            "runner": "emit_market_raw_once",
            "version": "v3",
        },
    }

    out_path = OUT_DIR / f"{now.date().isoformat()}.jsonl"

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")))
        f.write("\n")

    # -----------------------------------------------------------------
    # Summary: how many domain channels have both required symbols
    # -----------------------------------------------------------------

    ready = sum(
        1
        for ext, field in _DOMAIN_PAIRS.values()
        if ext in symbols and field in symbols
    )

    print(
        f"MARKET RAW EMITTED | "
        f"{len(symbols)}/{len(TICKER_NAMES)} symbols | "
        f"{ready}/{len(_DOMAIN_PAIRS)} domains ready"
    )


if __name__ == "__main__":
    main()
