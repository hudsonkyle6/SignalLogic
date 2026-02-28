#!/usr/bin/env python3
"""
Signal Hydro — Daily Run
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
from signal_core.core.lighthouse import annotate_packet
from signal_core.core.spillway_lighthouse import assess_spillway, SpillwayRoute


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
    afterglow_decay = float(packet.afterglow_decay) if packet.afterglow_decay is not None else 0.5

    wave = Wave.create(
        text=json.dumps(
            packet.__dict__,
            sort_keys=True,
            separators=(",", ":"),
        ),
        signal_type=f"{packet.domain}::{packet.lane}::{packet.channel}",
        phase=diurnal_phase,        # position in the dominant daily cycle
        frequency=dominant_hz,      # anchor frequency for this domain
        amplitude=amplitude,        # coherence carrier
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

    print(f"HYDRO: drained={len(packets)}")

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

        ingress = hydro_ingress_gate(packet)
        print(f"INGRESS: {ingress.gate_result.value} {ingress.reason}")

        # -------------------------------------------------------------
        # D0 — REJECT
        # -------------------------------------------------------------
        if ingress.gate_result == GateResult.REJECT:
            rejected += 1
            continue

        decision = dispatch(packet, ingress)
        print(f"DISPATCH: {decision.route.value} {decision.rule_id}"
              + (f" [observe band={packet.seasonal_band} fp={packet.forest_proximity:.2f}]"
                 if decision.observe and packet.seasonal_band else ""))

        # -------------------------------------------------------------
        # MAIN — sole penstock authority
        # When observe=True (watch zone), also send to Turbine.
        # -------------------------------------------------------------
        if decision.route.name == "MAIN":
            commit_packet(packet)
            append_audit(packet, ingress.gate_result.value, "MAIN")
            committed += 1
            print(f"COMMIT: OK (MAIN) decay={packet.afterglow_decay}")
            if decision.observe:
                obs = process_turbine(packet, f"{decision.rule_id}_OBSERVED")
                turbine_obs += 1
                print(f"TURBINE: observe band={packet.seasonal_band} "
                      f"fp={packet.forest_proximity:.2f} {obs.convergence_note}")
            continue

        # -------------------------------------------------------------
        # TURBINE — exploratory basin, phase convergence detection
        # -------------------------------------------------------------
        if decision.route.name == "TURBINE":
            obs = process_turbine(packet, decision.rule_id)
            append_audit(packet, ingress.gate_result.value, "TURBINE")
            turbine_obs += 1
            print(f"TURBINE: {obs.convergence_note} phase={obs.diurnal_phase:.3f} ({decision.rule_id})")
            continue

        # -------------------------------------------------------------
        # SPILLWAY — auxiliary lighthouse second look
        # -------------------------------------------------------------
        if decision.route.name == "SPILLWAY":
            spill = assess_spillway(packet)
            print(f"SPILLWAY: {spill.route.value} {spill.reason}")

            if spill.route == SpillwayRoute.RETURN:
                obs = process_turbine(packet, "SL_RETURN_TURBINE")
                turbine_obs += 1
                print(f"TURBINE (spillway return): {obs.convergence_note}")
            elif spill.route == SpillwayRoute.QUARANTINE:
                spillway_quarantined += 1
                print(f"ALERT: packet={packet.packet_id} quarantined by auxiliary lighthouse")
            elif spill.route == SpillwayRoute.HOLD:
                spillway_hold += 1
            # HOLD → no further action this cycle; packet stays in spillway basin
            continue

        # -------------------------------------------------------------
        # DROP — nothing to do
        # -------------------------------------------------------------
        print("COMMIT: SKIP (DROP route)")

    # -----------------------------------------------------------------
    # Post-cycle: turbine convergence summary
    # Always run — returns empty summary if no turbine observations.
    # -----------------------------------------------------------------
    convergence = run_turbine_summary()

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


if __name__ == "__main__":
    result = main()
    print(f"\nCYCLE COMPLETE: committed={result.committed} "
          f"turbine={result.turbine_obs} "
          f"quarantined={result.spillway_quarantined}")
