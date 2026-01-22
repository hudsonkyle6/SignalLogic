from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import math

from rhythm_os.core.field import compute_field
from apps.signal_company_os.adapters.signal_light_press import get_kernel_observables


def _json_safe(value):
    """
    Adapter-side JSON normalization.
    Converts non-finite floats (inf, -inf, nan) to None.
    Leaves all other values unchanged.
    """
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
    return value


def _normalize_dict(d: dict) -> dict:
    """
    Apply JSON-safe normalization to a flat dict.
    """
    return {k: _json_safe(v) for k, v in d.items()}


def generate_envelope(timestamp: float | None = None) -> Path:
    """
    Phase 1 lawful envelope generator.
    WRITE-ONLY.
    No ingestion, no validation, no posture logic.
    """

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).timestamp()

    ts_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # 1. Universal Field → Oracle geometry (physics → language boundary)
    # ------------------------------------------------------------------
    field = compute_field(timestamp)

    oracle_geometry = {
        "timestamp": field.t,          # canonical boundary translation
        "phases": dict(field.phases),
        "coherence": field.coherence,
    }

    # ------------------------------------------------------------------
    # 2. Domain observables (Signal Light Press)
    # ------------------------------------------------------------------
    kernel_obs_raw = get_kernel_observables(lookback_hours=24)
    kernel_obs = _normalize_dict(kernel_obs_raw)

    # ------------------------------------------------------------------
    # 3. Optional Sage context (descriptive only)
    # ------------------------------------------------------------------
    sage_context = {
        "domain": "signal_light_press",
        "observables": kernel_obs,
    }

    # ------------------------------------------------------------------
    # 4. Envelope identity
    # ------------------------------------------------------------------
    envelope_id = hashlib.sha256(ts_iso.encode()).hexdigest()[:12]

    envelope = {
        "envelope_id": envelope_id,
        "timestamp_utc": ts_iso,
        "oracle_geometry": oracle_geometry,
        "sage_context": sage_context,
        "shepherd_posture": "SILENT",
    }

    # ------------------------------------------------------------------
    # 5. Serialize (append-only)
    # ------------------------------------------------------------------
    out_dir = (
        Path(__file__).parent.parent.parent
        / "storage"
        / "rhythm_envelopes"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / f"{envelope_id}.json"
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    return path


if __name__ == "__main__":
    p = generate_envelope()
    print(f"Envelope written → {p}")

