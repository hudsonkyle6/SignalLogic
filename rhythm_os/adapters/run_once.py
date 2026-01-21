from __future__ import annotations

import time
import uuid
from typing import Dict, Any, Optional

from rhythm_os.core.field import compute_field, materialize_field_waves
from rhythm_os.adapters.observe.synthetic_multi import (
    SyntheticChannelSpec,
    generate_multi_channel_synthetic,
)

# Oracle (geometry only)
from rhythm_os.domain.oracle.phase import (
    describe_alignment,
    summarize_convergence,
)
from rhythm_os.domain.oracle.convergence_logic import OracleConvergence
from rhythm_os.domain.oracle.phase_emitter import emit_oracle_phase

# Shepherd (sole authority)
from rhythm_os.domain.shepherd import run_shepherd

# Execution gate (inert)
from rhythm_os.domain.execution.gate import evaluate_execution_gate

# PRESENTATION ONLY (passive)
from rhythm_os.ui.signal_dashboard import render_signal_dashboard


def run_once(
    *,
    t_now: Optional[float] = None,
    run_id: Optional[str] = None,
    synthetic_channels: Optional[list[SyntheticChannelSpec]] = None,
    render_dashboard: bool = True,
) -> Dict[str, Any]:
    """
    Execute one full, sovereign Rhythm OS pass.

    This function:
    - Owns time
    - Computes field and domain observations
    - Runs Oracle (descriptive only)
    - Runs Shepherd (sole authority)
    - Evaluates execution gate (inert)
    - Optionally renders the diagnostic dashboard
    - Returns a complete envelope
    """

    # -----------------------------------------------------------------
    # 0. Time & Run ID
    # -----------------------------------------------------------------
    t_now = t_now or time.time()
    run_id = run_id or uuid.uuid4().hex

    # -----------------------------------------------------------------
    # 1. Sovereign Field
    # -----------------------------------------------------------------
    field_sample = compute_field(t_now)
    field_waves = materialize_field_waves(field_sample)

    # -----------------------------------------------------------------
    # 2. Domain Observation
    # -----------------------------------------------------------------
    domain_waves = []
    if synthetic_channels:
        domain_waves = generate_multi_channel_synthetic(
            t_now=t_now,
            channels=synthetic_channels,
        )

    # -----------------------------------------------------------------
    # 3. ORACLE — descriptive only (sealed)
    # -----------------------------------------------------------------
    oracle_descriptors = describe_alignment(
        t_ref=t_now,
        domain_waves=domain_waves,
    )

    convergence_engine = OracleConvergence(
        within_deg=30.0,
        min_channels=3,
    )

    oracle_convergence = convergence_engine.summarize(
        t_now=t_now,
        descriptors=oracle_descriptors,
    )

    oracle_phase = emit_oracle_phase(
        oracle_convergence=oracle_convergence,
        source_run_id=run_id,
    )

    # -----------------------------------------------------------------
    # 4. SAGE — optional advisory context
    # -----------------------------------------------------------------
    sage_context = None
    try:
        from rhythm_os.domain.sage import run_sage

        sage_context = run_sage(
            oracle_descriptors=oracle_descriptors,
            oracle_convergence=oracle_convergence,
        )
    except ImportError:
        pass

    # -----------------------------------------------------------------
    # 5. SHEPHERD — sole authority
    # -----------------------------------------------------------------
    shepherd_posture = run_shepherd(
        oracle_convergence=oracle_convergence,
        sage_context=sage_context,
    )

    # -----------------------------------------------------------------
    # 6. EXECUTION GATE — inert, declarative
    # -----------------------------------------------------------------
    execution_gate = evaluate_execution_gate(
        shepherd_posture=shepherd_posture,
    )

    # -----------------------------------------------------------------
    # 7. DASHBOARD — presentation only (no authority)
    # -----------------------------------------------------------------
    if render_dashboard:
        render_signal_dashboard(
            t=t_now,
            field_sample=field_sample,
            field_waves=field_waves,
            domain_waves=domain_waves,
            oracle_descriptors=oracle_descriptors,
            oracle_convergence=oracle_convergence,
            oracle_phase=oracle_phase,
            shepherd_posture=shepherd_posture,
            execution_gate=execution_gate,
            context=sage_context or {},
        )

    # -----------------------------------------------------------------
    # 8. Return Envelope
    # -----------------------------------------------------------------
    return {
        "run_id": run_id,
        "t": t_now,
        "field_sample": field_sample,
        "field_waves": field_waves,
        "domain_waves": domain_waves,
        "oracle_descriptors": oracle_descriptors,
        "oracle_convergence": oracle_convergence,
        "oracle_phase": oracle_phase,
        "sage_context": sage_context,
        "shepherd_posture": shepherd_posture,
        "execution_gate": execution_gate,
    }
