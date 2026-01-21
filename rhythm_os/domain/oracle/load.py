from __future__ import annotations
from pathlib import Path
import json
from typing import List, Dict


def load_domain_waves_jsonl(path: Path) -> List[Dict]:
    """
    Load raw domain wave records from a JSON Lines file.

    This function performs no validation, normalization, filtering,
    ordering, or interpretation of records.
    It preserves records exactly as stored and returns them verbatim.

    Missing files yield an empty list.
    No judgment of record quality, relevance, or correctness is made here.
    """

    waves: List[Dict] = []

    if not path.exists():
        return waves

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Records are appended verbatim.
            # No schema enforcement or semantic interpretation occurs at this layer.
            waves.append(json.loads(line))

    return waves
