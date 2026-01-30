from __future__ import annotations

import time
import uuid
import math
from pathlib import Path
from typing import Dict, Any

# Core signal company imports (adjust paths as your repo evolves)
from apps.signal_company_os.core.psr.ledger import load_psr_events
from apps.signal_company_os.forge.infrastructure.readiness import (
    build_readiness_inputs,
    evaluate_readiness_criteria,
    ReadinessReport,
)
from apps.signal_company_os.forge.infrastructure.interval_mandate import IntervalMandate
from apps.signal_company_os.forge.infrastructure.psr import (
    PSREvent,
    compute_trust,
    scar_conditioning,
    get_recent_scar_weights,
)
from apps.signal_company_os.forge.human_gate_adapter import human_gate_prompt
from apps.signal_company_os.forge.run_interval import run_interval

# ── Layer 5/6/7 bridges (these should come from actual computations) ──
from apps.signal_company_os.antifragile.state import compute_antifragile_state
from apps.signal_company_os.oracle.oracle_layer4 import get_latest_oracle_snapshot
from apps.signal_company_os.lighthouse.predict_resonance import predict_next_resonance
from apps.signal_company_os.dark_field.loader import load_recent_domain_waves


def compute_readiness_score() -> ReadinessReport:
    """
    Real-ish readiness computation — pulls from actual layers instead of mocks.
    Returns ReadinessReport with .ready (bool), .score (0–1), .justification (str)
    """
    # Load recent residue
    recent_waves = load_recent_domain_waves(days=7)

    # Antifragile envelopes (Layer 5)
    af_state = compute_antifragile_state(recent_waves)
    af_i = (1 - af_state.get("drift", 0.5)) * \
           (1 - af_state.get("brittleness", 0.5)) * \
           (1 - af_state.get("strain", 0.5))

    # Oracle convergence (Layer 6 — simplified)
    oracle_snap = get_latest_oracle_snapshot()
    oc_i = (
        oracle_snap.get("HCFIndex", 0.6) +
        oracle_snap.get("OHI", 0.7) +
        (1 - abs(oracle_snap.get("Bias", 0.0))) / 3.0
    ) / 2.5  # rough normalization

    # Predictive outlook (Layer 7 lighthouse)
    pred_res = predict_next_resonance(recent_waves)
    po_i = pred_res.get("predicted_value", 0.65) * \
           {"Aligned": 1.0, "Converging": 0.85, "Drifting": 0.55}.get(
               pred_res.get("predicted_state", "Drifting"), 0.55
           )

    # Scar penalty
    psr_events = load_psr_events(limit=90)
    scars = get_recent_scar_weights(psr_events, decay_rate=0.08)
    sw_p = min(sum(scars), 0.50)

    # Composite (weights from earlier proposal)
    weights = {"af": 0.40, "oc": 0.30, "po": 0.20, "sw": 0.10}
    score = (
        weights["af"] * af_i +
        weights["oc"] * oc_i +
        weights["po"] * po_i -
        weights["sw"] * sw_p
    )
    score = max(0.0, min(1.0, score))

    ready = score >= 0.75
    justification = (
        f"READINESS {'GRANTED' if ready else 'DENIED'} — score={score:.3f}\n"
        f"  AF_i={af_i:.3f}  OC_i={oc_i:.3f}  PO_i={po_i:.3f}  SW_p={sw_p:.3f}\n"
        f"  drift={af_state.get('drift', '?'):.3f}, brittleness={af_state.get('brittleness', '?'):.3f}"
    )

    return ReadinessReport(
        ready=ready,
        score=score,
        justification=justification,
        breakdown={"AF_i": af_i, "OC_i": oc_i, "PO_i": po_i, "SW_p": sw_p}
    )


def run_lookout_daily(dry_run: bool = False):
    """
    Daily lookout cycle — the living spine of AUD.
    Observes → evaluates readiness → proposes → gates → executes (or silences).
    """
    print(f"[Lookout {time.strftime('%Y-%m-%d %H:%M:%S')}] Starting daily cycle")

    # 1. Load endurance & trust baseline
    psr_events = load_psr_events(limit=120)
    endurance_cycles = sum(1 for e in psr_events if e.get("event") == "ENDURANCE")
    recent_scar_count = sum(1 for e in psr_events[-10:] if e.get("event") in ("INTERVAL_FAILED", "GATE_DENIED"))
    events_typed = [PSREvent.from_dict(e) for e in psr_events]  # assuming from_dict helper exists
    trust = compute_trust(events_typed)
    scope_multiplier = scar_conditioning(trust, recent_scar_count)

    print(f"  Endurance cycles: {endurance_cycles} | Trust: {trust:.3f} | Scope mult: {scope_multiplier:.3f}")

    # 2. Readiness gate (the real computation)
    report = compute_readiness_score()
    print(f"[DEBUG] Readiness score = {report.score:.3f}")

    print(report.justification)

    if not report.ready:
        print("[Lookout] SILENCE — criteria not satisfied. Exiting.")
        return

    print("[Lookout] READY — proposal window open")

    # 3. Construct bounded mandate proposal
    now = time.time()
    # Scale duration with trust/scope, clamp sensibly (30s–4h for now)
    base_duration = 3600  # 1 hour default
    duration = int(base_duration * max(0.4, min(3.0, scope_multiplier + trust)))
    duration = max(1800, min(14400, duration))   # 30 min – 4 hours

    mandate = IntervalMandate(
        mandate_id=str(uuid.uuid4()),
        created_ts=now,
        start_ts=now,
        end_ts=now + duration,
        domain_scope_whitelist=["core_self", "alignment", "memory"],  # conservative default
        task_whitelist=["observe", "archive", "decay", "oracle_update"],
        justification=(
            f"Daily lookout cycle — readiness score {report.score:.3f}, "
            f"trust {trust:.3f}, scars conditioned to {scope_multiplier:.3f}"
        ),
        requesting_cycle_id="daily-" + time.strftime("%Y%m%d"),
    )

    # 4. Human sovereignty gate
    gate_summary = f"""
DAILY INTERVAL PROPOSAL
───────────────────────
ID:          {mandate.mandate_id[:8]}…
Duration:    {duration//3600}h {duration%3600//60}m
Scope:       {', '.join(mandate.domain_scope_whitelist)}
Tasks:       {', '.join(mandate.task_whitelist)}
Justification: {mandate.justification}
Readiness:   {report.score:.3f} ({report.breakdown})
Trust:       {trust:.3f}
"""
    decision = human_gate_prompt(gate_summary)

    if decision not in ("OPEN", "GRANTED", "APPROVE"):
        print("[Lookout] EXECUTION DENIED by human gate.")
        # Optionally log denial as scar
        return

    print(f"[Lookout] INTERVAL GRANTED — duration {duration}s")

    # 5. Execute bounded interval
    if dry_run:
        print("[Dry Run] Would execute interval now.")
        print(f"           Mandate: {mandate.model_dump_json(indent=2)}")
        return

    log_dir = Path("artifacts/interval_logs") / time.strftime("%Y-%m-%d")
    log_dir.mkdir(parents=True, exist_ok=True)

    result_path = run_interval(
        mandate=mandate,
        log_dir=log_dir,
        parent_cycle="daily_lookout",
    )

    print(f"[Lookout] INTERVAL COMPLETE — log: {result_path}")


if __name__ == "__main__":
    run_lookout_daily(dry_run=True)  # change to False when ready for live gate + execution
