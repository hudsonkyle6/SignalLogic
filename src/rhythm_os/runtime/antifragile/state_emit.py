# rhythm_os/runtime/antifragile/state_emit.py
"""
Antifragile Runtime Emitter (v1)

Thin, append-only, non-authoritative emitter that:
- reads recent DomainWaves from the canonical bus (dark_field JSONL)
- computes antifragile descriptor indices (0..1) via domain math
- emits computed DomainWaves back to the bus
- emits NOTHING when input is insufficient (silence is valid)
- de-duplicates emissions per (domain, channel, t_ref)

No scheduler. No optimizer. No gate. No controller.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rhythm_os.runtime.bus import (
    load_recent_domain_waves,
    today_bus_file,
    has_emission_at_time,
)

from rhythm_os.psr.append_domain_wave import append_domain_wave

# Canonical DomainWave import (see §10.1 wiring task)
# If you haven't unified yet, adjust this import temporarily to match your current tree.
from rhythm_os.domain.domain_wave import DomainWave

from rhythm_os.domain.antifragile.state import compute_antifragile_state


def _safe_float(x) -> Optional[float]:
    try:
        v = float(x)
        if v != v:  # NaN check
            return None
        return v
    except Exception:
        return None


def emit_antifragile_state(
    bus_dir: Path,
    t_ref: float,
    history_window_sec: float,
    source_domain: str,
    source_channel: str,
    baseline_n: int = 12,
    strain_window_n: int = 12,
    rest_factor: str = "none",
    emit_drift_if_missing: bool = False,
    cycle_id: Optional[str] = None,
    version: str = "v1",
) -> None:
    """
    Emits antifragile descriptor indices as DomainWaves:
      - unknowns_index
      - strain_index
      - brittleness_index
    Optionally emits drift_index ONLY if not emitted elsewhere and emit_drift_if_missing=True.

    SILENCE RULES:
    - If bus read returns insufficient source samples, return quietly.
    - If computed value is NaN/None, return quietly for that channel.
    - No dummy zeros.
    """

    # Load recent waves (silence is valid)
    waves = load_recent_domain_waves(
        bus_dir=bus_dir,
        t_ref=t_ref,
        history_window_sec=history_window_sec,
    )

    # Extract configured source series
    src = [
        w
        for w in waves
        if getattr(w, "domain", None) == source_domain
        and getattr(w, "channel", None) == source_channel
    ]

    series: List[float] = []
    for w in src:
        v = _safe_float(getattr(w, "phase_diff", None))
        if v is None:
            continue
        series.append(abs(v))

    # Need at least 2 samples to form "current" + baseline/history
    if len(series) < 2:
        return

    # Build conservative run_state
    current_scalar = series[-1]

    baseline_window = series[-(baseline_n + 1) : -1]
    load_history = series[-(strain_window_n + 1) : -1]

    # Minimum history requirement for strain/brittleness context.
    # If you want stricter silence, raise these thresholds.
    if len(baseline_window) < 1:
        return
    if len(load_history) < 3:
        return

    unknowns_index = 1.0  # v1 policy: default max unknowns unless upstream provides

    run_state = {
        "unknowns_index": unknowns_index,
        "current_scalar": current_scalar,
        "baseline_window": baseline_window,
        "recent_load": current_scalar,
        "load_history": load_history,
        "rest_factor": rest_factor,
    }

    # Compute descriptive indices (no gating)
    state = compute_antifragile_state(run_state)
    if not isinstance(state, dict):
        return

    # Extract channels we are responsible for in v1
    # NOTE: drift_index is emitted by runtime.reserve.emit_drift_index in the current cycle.
    # This module MUST NOT emit drift unless emit_drift_if_missing=True and drift is absent.
    channels = ["unknowns_index", "strain_index", "brittleness_index"]

    if emit_drift_if_missing:
        channels.append("drift_index")

    # Construct extractor provenance
    src_label = f"{source_domain}:{source_channel}"
    if cycle_id is None:
        # Deterministic-ish label: do NOT include random entropy.
        # t_ref is already the cycle anchor; if you want full determinism, set cycle_id upstream.
        cycle_id = f"antifragile_state@{int(t_ref)}"

    extractor = {
        "cycle_id": cycle_id,
        "source": src_label,
        "method": "compute_antifragile_state(run_state) from abs(phase_diff) series",
        "version": version,
        "baseline_n": str(baseline_n),
        "strain_window_n": str(strain_window_n),
        "unknowns_policy": "default_1.0",
    }

    # Enforce upstream-source discipline: source MUST exist
    if not extractor.get("source"):
        return

    out_path = today_bus_file(bus_dir=bus_dir, t_ref=t_ref)

    # Emit in stable order (unknowns first)
    for ch in channels:
        # If drift already emitted at this t_ref, skip it unless explicitly allowed.
        if ch == "drift_index" and not emit_drift_if_missing:
            continue

        if has_emission_at_time(
            bus_dir=bus_dir, t_ref=t_ref, domain="antifragile", channel=ch
        ):
            continue

        val = _safe_float(state.get(ch))
        if val is None:
            continue

        # Clamp softly to [0, 1] without inventing certainty
        if val < 0.0:
            val = 0.0
        if val > 1.0:
            val = 1.0

        wave = DomainWave(
            t=t_ref,
            domain="antifragile",
            channel=ch,
            field_cycle="computed",
            phase_external=0.0,
            phase_field=0.0,
            phase_diff=val,  # scalar payload carrier
            coherence=None,
            extractor=extractor,
        )

        append_domain_wave(out_path, wave)
