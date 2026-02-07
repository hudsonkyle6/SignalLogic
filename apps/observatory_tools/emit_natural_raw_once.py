from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------
# Natural RAW emitter (Observatory-side)
# Writes ONLY raw records to dark_field/natural/.
# No DomainWave objects. No PSR imports. Append-only.
# ---------------------------------------------------------------------

OUT_DIR = Path("src/rhythm_os/data/dark_field/natural")

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    now = float(time.time())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.jsonl"

    # Minimal RAW payload shape that PSR can project from:
    # (phase/coherence are measurements, not decisions)
    record = {
        "t": now,
        "domain": "natural_raw",
        "lane": "natural",
        "channel": "helix_projection",
        "field_cycle": "computed",
        "window_s": 7 * 24 * 3600,
        "data": {
            # NOTE: Replace these with real observed values once your
            # natural lane loader is wired. For now, this is a boot record.
            "phase_external": 0.0,
            "phase_field": 0.0,
            "phase_diff": 0.0,
            "coherence": None,
        },
        "extractor": {
            "source": "signal_observatory.natural",
            "runner": "emit_natural_raw_once",
            "version": "v1",
        },
    }

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"OBSERVATORY: wrote 1 natural raw record -> {out_path}")

if __name__ == "__main__":
    main()
