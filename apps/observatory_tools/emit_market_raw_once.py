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

Emits one raw market observation per run.
If data unavailable or incomplete → silent exit.
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
# Main
# ---------------------------------------------------------------------

def main() -> None:
    now = datetime.now(timezone.utc)

    tickers = ["^GSPC", "^VIX"]

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
    # Handle multi-index safely
    # -----------------------------------------------------------------

    try:
        close_sp = float(data["Close"]["^GSPC"].iloc[-1])
        close_vix = float(data["Close"]["^VIX"].iloc[-1])
    except Exception:
        print("MARKET RAW: incomplete multi-index structure")
        sys.exit(0)

    # -----------------------------------------------------------------
    # Reject NaN (never allow into dark field)
    # -----------------------------------------------------------------

    if close_sp != close_sp:  # NaN check
        print("MARKET RAW: SP500 not yet available")
        sys.exit(0)

    if close_vix != close_vix:
        print("MARKET RAW: VIX not yet available")
        sys.exit(0)

    # -----------------------------------------------------------------
    # Construct record
    # -----------------------------------------------------------------

    record = {
        "t": now.timestamp(),
        "domain": "market_raw",
        "lane": "market",
        "symbols": {
            "SP500": close_sp,
            "VIX": close_vix,
        },
        "extractor": {
            "source": "yfinance",
            "runner": "emit_market_raw_once",
            "version": "v2",
        },
    }

    out_path = OUT_DIR / f"{now.date().isoformat()}.jsonl"

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")))
        f.write("\n")

    print(
        f"MARKET RAW EMITTED | "
        f"SP500={close_sp:.2f} "
        f"VIX={close_vix:.2f}"
    )


if __name__ == "__main__":
    main()
