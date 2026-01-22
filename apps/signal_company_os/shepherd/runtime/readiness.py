"""
Shepherd Runtime — Input Readiness Evaluation
Authority: Signal Light Press
Classification: Protected Internal

Determines whether required inputs are:
- READY
- PRESENT_BUT_EMPTY
- MISSING

No interpretation. No scoring.
"""

from enum import Enum
from pathlib import Path


class InputStatus(str, Enum):
    READY = "READY"
    PRESENT_BUT_EMPTY = "PRESENT_BUT_EMPTY"
    MISSING = "MISSING"


def assess_json_readiness(path: Path) -> InputStatus:
    if not path.exists():
        return InputStatus.MISSING

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return InputStatus.PRESENT_BUT_EMPTY

    return InputStatus.READY
