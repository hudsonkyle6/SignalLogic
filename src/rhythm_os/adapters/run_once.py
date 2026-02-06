# run_once.py
"""
DIAGNOSTIC-ONLY MODULE

This script performs a single, read-only observatory pass:
- computes the sovereign field reference
- evaluates alignment and convergence geometry
- renders optional diagnostic visualization

It CANNOT:
- authorize action
- emit actuation packets
- open execution gates
- evaluate mandates
- express or imply authority of any kind

System posture: OBSERVATORY_ONLY
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, Any, Optional

from rhythm_os.core.field import compute_field, materialize_field_waves
from rhythm_os.adapters.observe.synthetic_multi import (
    SyntheticChannelSpec,
    generate_multi_channel_synthetic,
)

# ORACLE — geometry & description only
from rhythm_os.domain.oracle.phase import describe_alignment
from rhythm_os.domain.oracle.convergence_logic import OracleConvergence
from rhythm_os.domain.oracle.phase_emitter import emit_oracle_phase

# PRESENTATION ONLY (passive, read-only)
from rhythm_os.ui.signal_dashboard import render_signal_dashboard


def run_once(
    *,
    t_now: Optional[float] = None,
    run_id: Optional[str] = None,
    synthetic_channels: Optional[list[SyntheticChannelSpec]] = None,
    render_dashboard: bool = True,
) -> Dict[str, Any]:
    """
    Execute one diagnostic observatory pass.

    This function:
    - computes the sovereign field reference
    - generates optional synthetic domain observations
    - runs Oracle geometry (descriptive only)
    - emits no authority, posture, or decisions
    - optionally renders a read-only diagnostic dashboard

    This function CANNOT:
    - authorize action
    - evaluate execution
    - open gates
    - respond to mandates
    """

    # -----------------------------------------------------------------
    # 0. Time & Run ID
    # -----------------------------------------------------------------
    t_now = t_now or time.time()
    run_id = run_id or uuid.uuid4().hex

    # -----------------------------------------------------------------
    # 1. Sovereign Field (physics only)
    # -----------------------------------------------------------------
    field_sample = compute_field(t_now)
    field_waves = materialize_field_waves(field_sample)

    # -----------------------------------------------------------------
    # 2. Domain Observation (optional synthetic input)
    # -----------------------------------------------------------------
    domain_waves = []
    if synthetic_channels:
        domain_waves = generate_multi_channel_synthetic(
            t_now=t_now,
            channels=synthetic_channels,
        )

    # -----------------------------------------------------------------
    # 3. ORACLE — descriptive geometry only
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
    # 4. DASHBOARD — presentation only (no authority)
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
        )

    # -----------------------------------------------------------------
    # 5. Return Diagnostic Envelope
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
    }
