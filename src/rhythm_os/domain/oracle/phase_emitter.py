#phase_emitter.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime, timezone

from rhythm_os.domain.oracle.convergence_logic import ConvergenceSummary


PhaseLabel = Literal[
    "STILL",
    "REFLECT",
    "PREPARE",
    "TEND",
    "BUILD",
    "HARVEST",
    "HOLD",
    "RECOVER",
    "TRANSITION",
]


@dataclass(frozen=True)
class OraclePhase:
    """
    Optional symbolic phase classification.

    Descriptive only.
    Grants no authority.
    Shepherd must ignore this output.
    """
    phase_label: Optional[PhaseLabel]
    phase_confidence: Optional[float]
    emitted_at: str
    source_run_id: str


def emit_oracle_phase(
    *,
    oracle_convergence: List[ConvergenceSummary],
    source_run_id: str,
) -> OraclePhase:
    """
    Canonical v0 phase emitter.

    Rules (minimal, powerless):
    - If no convergence summaries -> no phase (None)
    - If any cycle is HIGH -> TRANSITION (high systemic motion)
    - Else if any cycle is MODERATE -> PREPARE (pressure present)
    - Else -> STILL (low pressure)

    This is symbolic legibility only.
    Must never be used for authority.
    """
    emitted_at = datetime.now(timezone.utc).isoformat()

    if not oracle_convergence:
        return OraclePhase(
            phase_label=None,
            phase_confidence=None,
            emitted_at=emitted_at,
            source_run_id=source_run_id,
        )

    levels = [s.convergence for s in oracle_convergence]

    if "high" in levels:
        return OraclePhase(
            phase_label="TRANSITION",
            phase_confidence=None,
            emitted_at=emitted_at,
            source_run_id=source_run_id,
        )

    if "moderate" in levels:
        return OraclePhase(
            phase_label="PREPARE",
            phase_confidence=None,
            emitted_at=emitted_at,
            source_run_id=source_run_id,
        )

    # low / none only
    return OraclePhase(
        phase_label="STILL",
        phase_confidence=None,
        emitted_at=emitted_at,
        source_run_id=source_run_id,
    )
