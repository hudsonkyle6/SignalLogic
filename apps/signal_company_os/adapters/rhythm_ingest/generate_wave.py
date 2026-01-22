# apps/signal_company_os/adapters/rhythm_ingest/generate_wave.py

from __future__ import annotations

from pathlib import Path
import json


def generate_wave(envelope: dict) -> Path:
    """
    Phase 1 wave generator.
    WRITE-ONLY.
    Append-only artifact sealing.
    """

    out_dir = (
        Path(__file__).parent.parent.parent
        / "storage"
        / "waves"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    wave_id = envelope["envelope_id"]
    path = out_dir / f"{wave_id}.json"

    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path
