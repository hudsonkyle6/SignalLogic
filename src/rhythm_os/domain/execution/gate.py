from __future__ import annotations

from rhythm_os.foundations_runtime.execution_gate import ExecutionGateDecision


def evaluate_execution_gate(
    *,
    permission: bool,
) -> ExecutionGateDecision:
    """
    Canonical execution gate.

    Kernel rule:
    - permission == True  -> OPEN
    - permission == False -> CLOSED
    """

    if permission:
        return ExecutionGateDecision(
            state="OPEN",
            reason="execution permission granted",
        )

    return ExecutionGateDecision(
        state="CLOSED",
        reason="execution permission not granted",
    )
