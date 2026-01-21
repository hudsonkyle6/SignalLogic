from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rhythm_os.domain.shepherd.shepherd import ShepherdPosture


GateState = Literal["CLOSED", "OPEN"]


@dataclass(frozen=True)
class ExecutionGateDecision:
    """
    Declarative execution gate.

    This object:
    - Authorizes no execution
    - Schedules nothing
    - Persists nothing
    - Exists only to state whether actions may exist at all
    """
    state: GateState
    reason: str


def evaluate_execution_gate(
    *,
    shepherd_posture: ShepherdPosture,
) -> ExecutionGateDecision:
    """
    Canonical execution gate evaluation.

    Rule:
    - ALLOW  -> OPEN
    - SILENT -> CLOSED
    - REFUSE -> CLOSED
    """

    if shepherd_posture.posture == "ALLOW":
        return ExecutionGateDecision(
            state="OPEN",
            reason="shepherd posture allows existence of action",
        )

    return ExecutionGateDecision(
        state="CLOSED",
        reason="shepherd posture does not permit action",
    )
