from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, List

from rhythm_os.domain.oracle.convergence_logic import ConvergenceSummary


Posture = Literal["SILENT", "REFUSE", "ALLOW"]


@dataclass(frozen=True)
class ShepherdPosture:
    """
    Shepherd governs whether action may exist at all.
    Emits posture only. No tasks. No prescriptions.
    """
    posture: Posture
    posture_confidence: Optional[float] = None
    reason: Optional[str] = None


def run_shepherd(
    *,
    oracle_convergence: List[ConvergenceSummary],
    sage_context: Optional[dict] = None,
) -> ShepherdPosture:
    """
    Shepherd Rule Set (Canonical):

    Rule 2 (highest priority):
    - If multiple field cycles show HIGH convergence simultaneously,
      REFUSE action due to contradiction.

    Rule 1:
    - If any convergence is MODERATE or HIGH,
      ALLOW continued observation.

    Default:
    - SILENT
    """

    # -------------------------------------------------
    # Rule 2 — Explicit refusal under contradiction
    # -------------------------------------------------
    high_cycles = {
        summary.field_cycle
        for summary in oracle_convergence
        if summary.convergence == "high"
    }

    if len(high_cycles) > 1:
        return ShepherdPosture(
            posture="REFUSE",
            posture_confidence=None,
            reason="conflicting high convergence across field cycles",
        )

    # -------------------------------------------------
    # Rule 1 — Permit observation under pressure
    # -------------------------------------------------
    for summary in oracle_convergence:
        if summary.convergence in ("moderate", "high"):
            return ShepherdPosture(
                posture="ALLOW",
                posture_confidence=None,
                reason="plural convergence detected; observation permitted",
            )

    # -------------------------------------------------
    # Default — armored silence
    # -------------------------------------------------
    return ShepherdPosture(
        posture="SILENT",
        posture_confidence=None,
        reason=None,
    )


    for summary in oracle_convergence:
        if summary.convergence in ("moderate", "high"):
            return ShepherdPosture(
                posture="ALLOW",
                posture_confidence=None,
                reason="plural convergence detected; observation permitted",
            )

    return ShepherdPosture(
        posture="SILENT",
        posture_confidence=None,
        reason=None,
    )
