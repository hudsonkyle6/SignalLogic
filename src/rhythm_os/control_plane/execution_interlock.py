from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import time

from rhythm_os.core.posture import SYSTEM_POSTURE
from .mandate import Mandate, is_fresh


@dataclass(frozen=True)
class InterlockDecision:
    allowed: bool
    reason: str


def may_actuate(
    mandate: Optional[Mandate], now: Optional[int] = None
) -> InterlockDecision:
    """
    The only permissible "permission check" in the system.

    OBSERVATORY_ONLY posture:
      - Always denies actuation, even with a mandate.
      - This is intentional: the instrument must not move water.

    In a future posture change, this function remains the single choke point.
    """
    if SYSTEM_POSTURE == "OBSERVATORY_ONLY":
        return InterlockDecision(False, "posture=OBSERVATORY_ONLY")

    # Future posture paths (explicitly unreachable today)
    if mandate is None:
        return InterlockDecision(False, "missing_mandate")

    t = int(time.time()) if now is None else int(now)
    if not is_fresh(mandate, now=t):
        return InterlockDecision(False, "stale_or_expired_mandate")

    return InterlockDecision(True, "fresh_mandate")
