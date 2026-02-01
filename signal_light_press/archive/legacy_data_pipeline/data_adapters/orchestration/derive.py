from datetime import datetime
from typing import Dict, Any


def derive_source(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive signals from a single normalized source.

    Rules:
    - Deterministic transforms only
    - No interpretation
    - No IO
    """
    if not isinstance(data, dict):
        return {}

    # Placeholder: pass-through for now
    return dict(data)


def derive_all(normalized: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Derive signals across all sources.
    """
    derived = {
        source: derive_source(payload)
        for source, payload in normalized.items()
    }

    derived["_meta"] = {
        "derived_at": datetime.utcnow().isoformat(),
        "derivation_version": "v0",
    }

    return derived
