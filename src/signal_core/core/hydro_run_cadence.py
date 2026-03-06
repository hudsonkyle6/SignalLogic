#!/usr/bin/env python3
"""
Signal Hydro — Cycle Cadence
POSTURE: HYDRO (SOLE PENSTOCK AUTHORITY)

Consumes admitted ingress packets and commits
sealed Waves to the Dark Field (penstock).

This module:
- DOES drain the ingress queue
- DOES structurally re-gate
- DOES dispatch (routing only)
- DOES commit to penstock (MAIN ONLY)
- DOES witness successful dispatches (audit)
- DOES run turbine summary at end of each cycle
- DOES NOT fabricate packets
- DOES NOT call observatory cycles

See rhythm_os/TWO_WATERS.md
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from signal_core.core.log import get_logger

log = get_logger(__name__)

from rhythm_os.core.wave.wave import Wave
from rhythm_os.core.dark_field.store import append_wave_from_hydro
from rhythm_os.runtime.temporal_anchor import compute_anchor

from signal_core.core.hydro_types import HydroPacket, GateResult
from signal_core.core.hydro_ingress_queue import drain_queue
from signal_core.core.hydro_ingress_gate import hydro_ingress_gate
from signal_core.core.hydro_dispatcher import dispatch
from signal_core.core.hydro_audit import append_audit
from signal_core.core.hydro_turbine import process_turbine
from signal_core.core.hydro_turbine_summary import run_turbine_summary
from signal_core.core.lighthouse import annotate_packet, attenuate_with_scars
from rhythm_os.core.memory.scar import (
    write_scar,
    apply_all_decay,
    pattern_key as _scar_pattern_key,
)
from signal_core.core.spillway_lighthouse import assess_spillway, SpillwayRoute
from signal_core.core.control_signal import emit_control_signal

# ---------------------------------------------------------------------
# Scar pressure constants
# ---------------------------------------------------------------------

# Base pressure added to the compound scar (forest edge + anomaly together).
# Kept separate from the fp component so the two addends are explicit at the call site.
_COMPOUND_SCAR_BASE_PRESSURE = 0.30

# Pressure written per strong convergence event per domain.
# Intentionally small — inert on its own; only meaningful when compounding
# with an existing forest_proximity scar on the same domain.
_CONVERGENCE_SCAR_PRESSURE = 0.15


# ---------------------------------------------------------------------
# Structured cycle result
# ---------------------------------------------------------------------


@dataclass
class CycleResult:
    """
    Structured summary of one complete hydro run cycle.

    All counts are non-negative integers.
    convergence_summary is None when no turbine observations exist this cycle.
    """

    cycle_ts: float
    packets_drained: int
    rejected: int
    committed: int
    turbine_obs: int
    spillway_quarantined: int
    spillway_hold: int
    convergence_summary: Optional[Dict[str, Any]] = field(default=None)
    # ReadinessStatus attached by run_full_cycle(); None when called directly.
    baseline_status: Optional[Any] = field(default=None)
    # ML prediction attached by run_full_cycle(); None until model is trained.
    # Keys: predicted_label, confidence, probabilities, model_version, calibrated.
    ml_prediction: Optional[Dict[str, Any]] = field(default=None)
    # Helm recommendation derived from cycle signals. Keys: state, rationale, ts.
    helm: Optional[Dict[str, Any]] = field(default=None)


# ---------------------------------------------------------------------
# Penstock commit
# ---------------------------------------------------------------------


def commit_packet(packet: HydroPacket) -> None:
    """
    Commit a single packet to the penstock as a sealed Wave.

    Packet coherence is mapped into Wave amplitude.
    Temporal anchor phases are carried into Wave frequency and couplings.
    No inference. No transformation beyond clamping.
    """

    # Extract coherence from packet payload (authoritative)
    try:
        amplitude = float((packet.value or {}).get("coherence", 0.0) or 0.0)
    except Exception:
        amplitude = 0.0

    # Clamp to [0,1]
    amplitude = max(0.0, min(1.0, amplitude))

    # Prefer anchor phases stamped at the throat; compute from timestamp if absent.
    if packet.diurnal_phase is not None:
        diurnal_phase = float(packet.diurnal_phase)
        semi_diurnal_phase = float(packet.semi_diurnal_phase or 0.0)
        long_wave_phase = float(packet.long_wave_phase or 0.0)
        anchor = compute_anchor(float(packet.t), domain=packet.domain)
        dominant_hz = anchor.dominant_hz
    else:
        anchor = compute_anchor(float(packet.t), domain=packet.domain)
        diurnal_phase = anchor.diurnal_phase
        semi_diurnal_phase = anchor.semi_diurnal_phase
        long_wave_phase = anchor.long_wave_phase
        dominant_hz = anchor.dominant_hz

    # Couplings carry the secondary anchor phases alongside the wave.
    couplings = {
        "semi_diurnal": semi_diurnal_phase,
        "long_wave": long_wave_phase,
    }

    # Use Lighthouse afterglow_decay if available; fall back to stable default.
    afterglow_decay = (
        float(packet.afterglow_decay) if packet.afterglow_decay is not None else 0.5
    )

    wave = Wave.create(
        text=json.dumps(
            packet.__dict__,
            sort_keys=True,
            separators=(",", ":"),
        ),
        signal_type=f"{packet.domain}::{packet.lane}::{packet.channel}",
        phase=diurnal_phase,  # position in the dominant daily cycle
        frequency=dominant_hz,  # anchor frequency for this domain
        amplitude=amplitude,  # coherence carrier
        afterglow_decay=afterglow_decay,
        couplings=couplings,
    )

    append_wave_from_hydro(wave)


# ---------------------------------------------------------------------
# Main hydro cadence
# ---------------------------------------------------------------------


def main() -> CycleResult:
    """
    Daily hydro cadence.

    Sole responsibilities:
    - drain ingress queue
    - structurally re-gate
    - dispatch (route only)
    - commit MAIN waves
    - witness successful dispatches
    - run turbine convergence summary

    Returns a CycleResult with structured counts and summary.
    """
    cycle_ts = time.time()

    packets: List[HydroPacket] = drain_queue()

    log.info("hydro drained=%d", len(packets))

    rejected = 0
    committed = 0
    turbine_obs = 0
    spillway_quarantined = 0
    spillway_hold = 0

    for packet in packets:
        # ---------------------------------------------------------
        # Lighthouse annotation — stamp seasonal context BEFORE gate.
        # Gate is blind to these fields; dispatcher uses forest_proximity.
        # ---------------------------------------------------------
        packet = annotate_packet(packet)

        # Scar attenuation — reduce forest_proximity for patterns the system
        # has already survived.  Novel patterns are unaffected.
        packet = attenuate_with_scars(packet)

        ingress = hydro_ingress_gate(packet)
        log.debug(
            "ingress result=%s reason=%s", ingress.gate_result.value, ingress.reason
        )

        # -------------------------------------------------------------
        # D0 — REJECT
        # -------------------------------------------------------------
        if ingress.gate_result == GateResult.REJECT:
            rejected += 1
            continue

        decision = dispatch(packet, ingress)
        log.debug(
            "dispatch route=%s rule=%s%s",
            decision.route.value,
            decision.rule_id,
            f" band={packet.seasonal_band} fp={packet.forest_proximity:.2f}"
            if decision.observe and packet.seasonal_band
            else "",
        )

        # -------------------------------------------------------------
        # MAIN — sole penstock authority
        # When observe=True (watch zone), also send to Turbine.
        # -------------------------------------------------------------
        if decision.route.name == "MAIN":
            commit_packet(packet)
            emit_control_signal(packet, decision)
            append_audit(packet, ingress.gate_result.value, "MAIN")
            committed += 1
            log.info("commit route=MAIN decay=%s", packet.afterglow_decay)
            if decision.observe:
                obs = process_turbine(packet, f"{decision.rule_id}_OBSERVED")
                turbine_obs += 1
                log.debug(
                    "turbine observe band=%s fp=%.2f note=%s",
                    packet.seasonal_band,
                    packet.forest_proximity,
                    obs.convergence_note,
                )
            continue

        # -------------------------------------------------------------
        # TURBINE — exploratory basin, phase convergence detection
        # -------------------------------------------------------------
        if decision.route.name == "TURBINE":
            obs = process_turbine(packet, decision.rule_id)
            append_audit(packet, ingress.gate_result.value, "TURBINE")
            turbine_obs += 1
            log.debug(
                "turbine note=%s phase=%.3f rule=%s",
                obs.convergence_note,
                obs.diurnal_phase,
                decision.rule_id,
            )

            # Scar write — forest edge routing.
            # The system met this pattern at the margin and diverted rather
            # than committing.  Record the pressure so future encounters
            # carry less weight.
            if decision.rule_id == "DLH_TURBINE_FOREST_EDGE":
                fp = float(packet.forest_proximity or 0.0)
                write_scar(
                    domain=packet.domain,
                    key=_scar_pattern_key(packet.seasonal_band, packet.channel),
                    pressure_delta=fp,
                    changed=True,
                    trigger="forest_proximity",
                    pattern_confidence=float(packet.pattern_confidence or 1.0),
                )

            continue

        # -------------------------------------------------------------
        # SPILLWAY — auxiliary lighthouse second look
        # -------------------------------------------------------------
        if decision.route.name == "SPILLWAY":
            # Scar write — anomaly routed to spillway.
            # Write before the second-look so reinforcement reflects the
            # initial dispatch pressure, not the spillway outcome.
            if bool(packet.anomaly_flag):
                write_scar(
                    domain=packet.domain,
                    key=_scar_pattern_key(packet.seasonal_band, packet.channel),
                    pressure_delta=0.5,
                    changed=True,
                    trigger="anomaly",
                    pattern_confidence=float(packet.pattern_confidence or 1.0),
                )

            spill = assess_spillway(packet)
            log.debug("spillway route=%s reason=%s", spill.route.value, spill.reason)

            if spill.route == SpillwayRoute.RETURN:
                obs = process_turbine(packet, "SL_RETURN_TURBINE")
                turbine_obs += 1
                log.debug("turbine spillway-return note=%s", obs.convergence_note)
            elif spill.route == SpillwayRoute.QUARANTINE:
                spillway_quarantined += 1
                log.warning("quarantine packet_id=%s", packet.packet_id)
                # Compound scar — forest edge + anomaly together.
                # Heavier pressure: the system both didn't recognise the
                # territory AND detected structural irregularity.
                fp = float(packet.forest_proximity or 0.0)
                write_scar(
                    domain=packet.domain,
                    key=_scar_pattern_key(packet.seasonal_band, packet.channel),
                    pressure_delta=fp + _COMPOUND_SCAR_BASE_PRESSURE,
                    changed=True,
                    trigger="compound",
                    pattern_confidence=float(packet.pattern_confidence or 1.0),
                )
            elif spill.route == SpillwayRoute.HOLD:
                spillway_hold += 1
            # HOLD → no further action this cycle; packet stays in spillway basin
            continue

        # -------------------------------------------------------------
        # DROP — nothing to do
        # -------------------------------------------------------------
        log.debug("drop packet_id=%s", packet.packet_id)

    # -----------------------------------------------------------------
    # Post-cycle: scar decay — pressure fades unless reinforced each cycle.
    # -----------------------------------------------------------------
    scar_decay = apply_all_decay()
    if scar_decay:
        pruned_total = sum(scar_decay.values())
        if pruned_total:
            log.debug(
                "scar decay pruned=%d domains=%s", pruned_total, list(scar_decay.keys())
            )

    # -----------------------------------------------------------------
    # Post-cycle: turbine convergence summary
    # Always run — returns empty summary if no turbine observations.
    # -----------------------------------------------------------------
    convergence = run_turbine_summary()

    # -----------------------------------------------------------------
    # Post-cycle: strong convergence → provisional scar
    # When 3+ domains phase-align (strong event), write a small convergence
    # marker to each domain's scar store.  The key is phase-bucketed so
    # convergences at different times of day accumulate independently.
    # pressure_delta=0.15 is intentionally small — it only meaningfully
    # attenuates when compounded with existing forest_proximity scars.
    # -----------------------------------------------------------------
    for event in convergence.get("convergence_events", []):
        if event.get("strength") != "strong":
            continue
        phase_bucket = int(float(event.get("diurnal_phase", 0)) * 12)
        conv_key = f"convergence:{phase_bucket}"
        for domain in event.get("domains", []):
            write_scar(
                domain=domain,
                key=conv_key,
                pressure_delta=_CONVERGENCE_SCAR_PRESSURE,
                changed=False,
                trigger="convergence",
                pattern_confidence=1.0,  # convergence is phase-based, not seasonal
            )
            log.debug(
                "convergence scar domain=%s phase_bucket=%d domains=%s",
                domain,
                phase_bucket,
                ",".join(event.get("domains", [])),
            )

    return CycleResult(
        cycle_ts=cycle_ts,
        packets_drained=len(packets),
        rejected=rejected,
        committed=committed,
        turbine_obs=turbine_obs,
        spillway_quarantined=spillway_quarantined,
        spillway_hold=spillway_hold,
        convergence_summary=convergence,
    )


def _phase_to_period(phase: float) -> str:
    """Convert a diurnal phase [0, 1] to a human-readable time-of-day label."""
    hour = int(float(phase) * 24)
    if hour < 6:
        return "early morning"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "night"


def _run_voice_narration(result: "CycleResult") -> None:
    """
    Generate a narrator voice line from the cycle result and persist it.

    Errors are caught — voice never blocks or delays the cycle.
    Imports are deferred so the module loads even without Ollama installed.
    """
    try:
        from rhythm_os.voice.narrator import narrate
        from rhythm_os.voice.voice_store import VoiceLine, persist_voice_line

        cs = result.convergence_summary or {}

        # Build human-readable convergence event descriptions.
        convergence_detail = []
        for ev in cs.get("convergence_events", []):
            domains = sorted(ev.get("domains", []))
            strength = ev.get("strength", "weak")
            phase = ev.get("diurnal_phase", 0.0)
            period = _phase_to_period(phase)
            domain_str = " + ".join(domains)
            convergence_detail.append(
                f"{strength}: {domain_str} aligned during {period} (φ={phase:.3f})"
            )

        drained = result.packets_drained or 1
        committed = result.committed
        quarantined = result.spillway_quarantined
        admission_pct = f"{committed / drained * 100:.0f}%"
        anomaly_rate = quarantined / drained
        strong_events = cs.get("strong_events", 0)
        event_count = cs.get("convergence_event_count", 0)

        # Derive helm state using same logic as the dashboard.
        if anomaly_rate > 0.10:
            helm_state = "WAIT"
            helm_rationale = f"elevated anomalies ({quarantined} quarantined)"
        elif committed / drained < 0.50:
            helm_state = "WAIT"
            helm_rationale = f"low admission rate ({admission_pct})"
        elif strong_events > 0:
            helm_state = "WAIT"
            helm_rationale = "strong cross-domain convergence — conditions in flux"
        elif event_count > 0:
            helm_state = "PREPARE"
            helm_rationale = "domains beginning to align — conditions shifting"
        elif committed / drained > 0.88 and quarantined == 0:
            helm_state = "PUSH"
            helm_rationale = f"all domains clear ({admission_pct} admitted) — favorable window"
        else:
            helm_state = "ACT"
            helm_rationale = f"stable, nominal routing ({admission_pct} admitted)"

        cycle_summary = {
            "packets_admitted": committed,
            "packets_drained": result.packets_drained,
            "rejected": result.rejected,
            "turbine_obs": result.turbine_obs,
            "spillway_quarantined": quarantined,
            "admission_pct": admission_pct,
            "domains_seen": sorted(cs.get("domains_observed", {}).keys()),
            "convergence_events": event_count,
            "strong_events": strong_events,
            "convergence_detail": convergence_detail,
            "helm_state": helm_state,
            "helm_rationale": helm_rationale,
        }
        narration = narrate(cycle_summary)
        persist_voice_line(
            VoiceLine(mode="narrator", text=narration.text, raw=narration.raw)
        )
        log.info("voice narrator persisted text=%r", narration.text[:60])
    except Exception as exc:
        log.debug("voice narration skipped: %s", exc)


def _run_voice_interpretation(convergence: "dict") -> None:
    """
    For each strong convergence event, record domain-pair observations in
    ConvergenceMemoryStore and run the LLM interpreter over the resulting
    history summary.  Only strong events (3+ domains) trigger interpretation.

    Errors are caught — voice never blocks or delays the cycle.
    """
    try:
        from itertools import combinations

        from rhythm_os.domain.convergence.memory_store import ConvergenceMemoryStore
        from rhythm_os.voice.interpreter import interpret
        from rhythm_os.voice.voice_store import VoiceLine, persist_voice_line

        strong_events = [
            e
            for e in convergence.get("convergence_events", [])
            if e.get("strength") == "strong"
        ]
        if not strong_events:
            return

        store = ConvergenceMemoryStore()

        for event in strong_events:
            domains = sorted(event.get("domains", []))
            phase = float(event.get("diurnal_phase", 0.0))
            note = "convergence:" + ",".join(domains)

            for domain_a, domain_b in combinations(domains, 2):
                store.record(
                    domain_a=domain_a,
                    domain_b=domain_b,
                    diurnal_phase=phase,
                    leading_domain="",  # leading domain not determinable from summary
                    convergence_note=note,
                )
                history = dict(store.pair_summary(domain_a, domain_b))
                history["domain_pair"] = f"{domain_a}+{domain_b}"
                interp = interpret(history)
                vl = VoiceLine(
                    mode="interpreter",
                    text=f"{interp.convergence_type}: {interp.rationale}",
                    raw=interp.raw,
                )
                persist_voice_line(vl)
                log.info(
                    "voice interpreter persisted pair=%s+%s type=%s",
                    domain_a,
                    domain_b,
                    interp.convergence_type,
                )
    except Exception as exc:
        log.debug("voice interpretation skipped: %s", exc)


def _persist_cycle_result(result: "CycleResult") -> None:
    """Write CycleResult fields to TURBINE_DIR/last_cycle.json for the dashboard."""
    import dataclasses as _dc
    from rhythm_os.runtime.paths import TURBINE_DIR

    TURBINE_DIR.mkdir(parents=True, exist_ok=True)
    data = _dc.asdict(result)
    data.pop("baseline_status", None)  # ReadinessStatus object — not JSON-serializable
    path = TURBINE_DIR / "last_cycle.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


if __name__ == "__main__":
    import dataclasses as _dc

    from signal_core.core.log import configure

    configure()
    result = main()
    log.info(
        "cycle complete committed=%d turbine=%d quarantined=%d",
        result.committed,
        result.turbine_obs,
        result.spillway_quarantined,
    )

    # ML step 1: extract features from cycle result → data/ml/features.jsonl
    _features: dict = {}
    try:
        from signal_core.core.ml.feature_builder import extract_and_append

        _features = extract_and_append(result)
    except Exception:
        log.warning(
            "ml feature extraction failed — cycle result unaffected", exc_info=True
        )

    # ML step 2: inference — predict convergence event label
    if _features:
        try:
            from signal_core.core.ml.classifier import load_model, predict

            if load_model() is not None:
                _pred = predict(_features)
                log.info(
                    "ml prediction label=%s confidence=%.1f%% model=%s",
                    _pred.predicted_label,
                    _pred.confidence * 100,
                    _pred.model_version,
                )
                result = _dc.replace(
                    result,
                    ml_prediction={
                        "predicted_label": _pred.predicted_label,
                        "confidence": _pred.confidence,
                        "probabilities": _pred.probabilities,
                        "model_version": _pred.model_version,
                        "calibrated": _pred.calibrated,
                    },
                )
        except Exception:
            log.warning("ml inference failed — cycle result unaffected", exc_info=True)

    # Helm step: derive operational posture recommendation and attach to result.
    try:
        import dataclasses as _dc2

        cs_ = result.convergence_summary or {}
        _drained = result.packets_drained or 1
        _anom_rate = result.spillway_quarantined / _drained
        _adm_rate = result.committed / _drained
        _strong = cs_.get("strong_events", 0)
        _events = cs_.get("convergence_event_count", 0)
        _evlist = cs_.get("convergence_events", [])

        if _anom_rate > 0.10:
            _hstate, _hrat = "WAIT", f"elevated anomalies ({result.spillway_quarantined} quarantined)"
        elif _adm_rate < 0.50:
            _hstate, _hrat = "WAIT", f"low admission rate ({_adm_rate:.0%})"
        elif _strong > 0:
            _ev0 = next((e for e in _evlist if e.get("strength") == "strong"), {})
            _doms = " + ".join(sorted(_ev0.get("domains", [])))
            _hstate, _hrat = "WAIT", f"{_doms} converging strongly — conditions in flux"
        elif _events > 0:
            _ev0 = _evlist[0] if _evlist else {}
            _doms = " + ".join(sorted(_ev0.get("domains", [])))
            _hstate, _hrat = "PREPARE", f"{_doms} aligning — conditions shifting"
        elif _adm_rate > 0.88 and result.spillway_quarantined == 0:
            _hstate, _hrat = "PUSH", f"all domains clear ({_adm_rate:.0%} admitted)"
        else:
            _hstate, _hrat = "ACT", f"stable, nominal routing ({_adm_rate:.0%} admitted)"

        result = _dc2.replace(
            result,
            helm={"state": _hstate, "rationale": _hrat, "ts": result.cycle_ts},
        )
        log.info("helm recommendation state=%s", _hstate)
    except Exception:
        log.debug("helm recommendation skipped", exc_info=True)

    _persist_cycle_result(result)
    _run_voice_narration(result)
    _run_voice_interpretation(result.convergence_summary or {})
