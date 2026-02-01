from typing import Dict, Any


def normalize_source(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single input source.

    Rules:
    - No math
    - No interpretation
    - Deterministic only
    """
    if not isinstance(data, dict):
        return {}

    # Placeholder: pass-through for now
    return dict(data)


def normalize_all(raw_inputs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Normalize all input sources.
    """
    return {
        source: normalize_source(payload)
        for source, payload in raw_inputs.items()
    }
