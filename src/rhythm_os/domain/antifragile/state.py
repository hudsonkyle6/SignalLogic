# rhythm_os/domain/antifragile/state.py

from typing import Dict, Any

from rhythm_os.domain.antifragile.drift import compute_drift_index
from rhythm_os.domain.antifragile.brittleness import compute_brittleness_index
from rhythm_os.domain.antifragile.strain import compute_strain_index


def compute_antifragile_state(run_state: Dict[str, Any]) -> Dict[str, float]:
    """
    Compose antifragile descriptor state from run-state references.

    This function performs no evaluation, gating, or decision-making.
    It aggregates independently computed antifragile descriptors
    into a single descriptive record.

    All returned values are normalized indices in [0, 1].
    """

    unknowns = run_state.get("unknowns_index", 1.0)

    drift = compute_drift_index(
        current=run_state.get("current_scalar", 0.0),
        baseline=run_state.get("baseline_window", []),
    )

    strain = compute_strain_index(
        recent_load=run_state.get("recent_load"),
        load_history=run_state.get("load_history"),
        rest_factor=run_state.get("rest_factor"),
    )

    brittleness = compute_brittleness_index(
        run_state,
        unknowns_index=unknowns,
    )

    return {
        "unknowns_index": unknowns,
        "drift_index": drift,
        "strain_index": strain,
        "brittleness_index": brittleness,
    }
