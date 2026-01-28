from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessInputs:
    endurance_cycles: int
    avg_envelope: float
    convergence_fraction: float
    recent_scar_count: int
    trust: float


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    justification: str


def evaluate_readiness_criteria(inputs: ReadinessInputs) -> ReadinessReport:
    """
    Deterministic readiness evaluation.

    This function:
    - performs no mutation
    - makes no decisions
    - applies fixed criteria only
    """

    reasons = []

    if inputs.endurance_cycles < 3:
        reasons.append("Insufficient endurance cycles")

    if inputs.avg_envelope > 0.30:
        reasons.append("Envelope instability too high")

    if inputs.convergence_fraction < 0.75:
        reasons.append("Insufficient convergence")

    if inputs.trust < 0.6:
        reasons.append("Trust below minimum threshold")

    if inputs.recent_scar_count > 2:
        reasons.append("Excessive recent scar count")

    if reasons:
        return ReadinessReport(
            ready=False,
            justification="; ".join(reasons),
        )

    return ReadinessReport(
        ready=True,
        justification="Endurance, convergence, and trust criteria satisfied",
    )


@dataclass(frozen=True)
class ReadinessSnapshot:
    inputs: ReadinessInputs
    ready: bool
    rationale: str


def build_readiness_inputs(
    *,
    endurance_cycles: int,
    avg_envelope: float,
    convergence_fraction: float,
    recent_scar_count: int,
    trust: float,
) -> ReadinessInputs:
    """
    Assemble readiness inputs without interpretation.
    No thresholds. No logic. Pure struct.
    """
    return ReadinessInputs(
        endurance_cycles=endurance_cycles,
        avg_envelope=avg_envelope,
        convergence_fraction=convergence_fraction,
        recent_scar_count=recent_scar_count,
        trust=trust,
    )
