from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GateState = Literal["CLOSED", "OPEN"]


@dataclass(frozen=True)
class ExecutionGateDecision:
    """
    Declarative execution gate decision.

    Properties:
    - authorizes no execution
    - schedules nothing
    - persists nothing
    - describes only whether execution may exist
    """
    state: GateState
    reason: str
