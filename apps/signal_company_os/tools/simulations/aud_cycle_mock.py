from __future__ import annotations

import time
import uuid
from pathlib import Path

from forge.infrastructure.readiness import (
    ReadinessInputs,
    evaluate_readiness_criteria,
)
from forge.infrastructure.interval_mandate import IntervalMandate
from forge.infrastructure.psr import PSREvent, compute_trust, scar_conditioning
from forge.gate import human_gate_prompt
from forge.run_interval import run_interval


def mock_cycle():
    """
    End-to-end AUD simulation:
    - mock envelopes / convergence
    - compute readiness
    - human gate
    - interval execution
    """

    # --- Mock observed history ---
    events = [
        PSREvent("ENDURANCE"),
        PSREvent("ENDURANCE"),
        PSREvent("ENDURANCE"),
        PSREvent("ENDURANCE"),
        PSREvent("INTERVAL_OK"),
    ]

    trust = compute_trust(events)
    recent_scar_count = 0
    scope_multiplier = scar_conditioning(trust, recent_scar_count)

    # --- Mock readiness inputs ---
    readiness_inputs = ReadinessInputs(
        endurance_cycles=4,
        avg_envelope=0.22,
        convergence_fraction=0.81,
        recent_scar_count=recent_scar_count,
        trust=trust,
    )

    report = evaluate_readiness_criteria(readiness_inputs)

    if not report.ready:
        print("[AUD] SILENCE — readiness criteria not met")
        print(report.justification)
        return

    print("[AUD] READY — proposal eligible")
    print(report.justification)
    print(f"[AUD] trust={trust:.2f}, scope_multiplier={scope_multiplier:.2f}")

    # --- Build interval proposal ---
    now = time.time()
    duration = int(60 * scope_multiplier) or 30

    mandate = IntervalMandate(
        mandate_id=str(uuid.uuid4()),
        created_ts=now,
        start_ts=now,
        end_ts=now + duration,
        domain_scope_whitelist=["core_self"],
        task_whitelist=["monitor_only"],
        justification="Mock AUD cycle — resemblance + endurance satisfied",
    )

    # --- Human gate ---
    decision = human_gate_prompt(
        summary=f"""
AUD INTERVAL PROPOSAL
---------------------
duration: {duration}s
tasks: {mandate.task_whitelist}
justification: {mandate.justification}
"""
    )

    if decision.decision != "GRANT":
        print(f"[AUD] HUMAN DECISION: {decision.decision}")
        return

    print("[AUD] INTERVAL GRANTED — executing")

    # --- Execute interval ---
    out = run_interval(
        mandate,
        log_dir=Path("artifacts/interval_logs")
    )

    print(f"[AUD] INTERVAL COMPLETE — log written to {out}")


if __name__ == "__main__":
    mock_cycle()
