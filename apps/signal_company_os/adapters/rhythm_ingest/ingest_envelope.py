# apps/signal_company_os/adapters/rhythm_ingest/ingest_envelope.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional
import hashlib

from rhythm_os.core.field import compute_field


def create_envelope(
    *,
    domain: str,
    observables: Dict[str, Optional[float]],
    timestamp: float | None = None,
    shepherd_posture: str = "SILENT",
) -> dict:
    """
    Phase 1 envelope constructor.
    PURE ASSEMBLY.
    No validation, no escalation, no side-effects.
    """

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).timestamp()

    ts_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    # Physics observation
    field = compute_field(timestamp)

    oracle_geometry = {
        "timestamp": field.t,
        "phases": dict(field.phases),
        "coherence": field.coherence,
    }

    envelope_id = hashlib.sha256(ts_iso.encode()).hexdigest()[:12]

    return {
        "envelope_id": envelope_id,
        "timestamp_utc": ts_iso,
        "oracle_geometry": oracle_geometry,
        "sage_context": {
            "domain": domain,
            "observables": observables,
        },
        "shepherd_posture": shepherd_posture,
    }
