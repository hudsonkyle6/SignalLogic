from datetime import datetime
from typing import List, Dict, Any

from rhythm_os.core.wave.wave import Wave


def attach_domain_metadata(waves: List[Wave], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach inert, non-authoritative metadata to newly minted Waves.

    Properties:
    - Pure function
    - No IO
    - No persistence
    - No evaluation
    - No posture or permission semantics
    """

    descriptors: Dict[str, Any] = {}

    return {
        "descriptors": descriptors,
        "_meta": {
            "attached_at": datetime.utcnow().isoformat(),
            "schema_version": "v0",
        },
    }
