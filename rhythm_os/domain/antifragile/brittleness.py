# rhythm_os/domain/antifragile/brittleness.py

from typing import Dict, Any


def clamp01(x: float) -> float:
    """
    Project input to the unit interval [0, 1] via saturation.

    Pure geometric normalization — no thresholds, no decisions,
    no authority, and no evaluative semantics.
    """
    return 0.0 if x <= 0.0 else 1.0 if x >= 1.0 else x


def compute_brittleness_index(
    run_state: Dict[str, Any],
    *,
    unknowns_index: float,
    total_commitment_slots: int = 8,
    total_dependency_checks: int = 6,
) -> float:
    """
    Compute a normalized index in [0, 1] from run-state reference values.

    Normalization rules:
    - Undefined reference values (e.g., irreversible_commitments or
      dependency_gaps missing from run_state) → maximal normalized
      contribution for that component
    - All other cases → envelope-based computation (see below)

    The components represent dimensionless reference proportions:
    - irreversible_commitments: proportion of committed slots
    - dependency_gaps: proportion of unmet dependency checks
    - unknowns_index: external normalized uncertainty indicator

    Each component is independently normalized to [0, 1].

    The final index is the maximum of the three normalized components.
    This is a conservative envelope selection — not a worst-case judgment,
    not prioritization, and not alarm logic.

    This function performs only dimensionless normalization.
    No physiological, evaluative, mechanical, or decision semantics
    are implied or permitted.
    """

    irreversible = run_state.get("irreversible_commitments", None)
    gaps = run_state.get("dependency_gaps", None)

    # Undefined reference inputs normalize to maximal contribution
    if irreversible is None:
        irreversible = total_commitment_slots
    if gaps is None:
        gaps = total_dependency_checks

    C = clamp01(irreversible / max(total_commitment_slots, 1))
    D = clamp01(gaps / max(total_dependency_checks, 1))
    U = clamp01(unknowns_index)

    # Conservative envelope selection across normalized components
    return max(C, D, U)
