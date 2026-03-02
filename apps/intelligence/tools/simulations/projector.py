from __future__ import annotations

from typing import Any, Dict


def project(domain_state: Dict[str, Any], *, started_at) -> Dict[str, Any]:
    """
    Reduce domain state into human-facing artifacts.

    Rules:
    - No IO
    - No mutation upstream
    - No authority
    - Deterministic formatting only
    """
    return {
        "posture": {},
        "signals": {},
        "_meta": {
            "projected_at": started_at.isoformat(),
            "projection_version": "v0",
        },
    }
