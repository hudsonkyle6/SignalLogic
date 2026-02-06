#alignment.py
from __future__ import annotations

from rhythm_os.runtime.cycle_id import compute_cycle_id
"""
Alignment Layer Runtime (Oracle geometry)

AUTHORITY: Signal Light Press
CLASSIFICATION: RUNTIME SUPPORT
EXECUTABLE: NO (library)
DECISION AUTHORITY: NONE

Emits descriptive oracle convergence summary as a DomainWave packet.
"""


from pathlib import Path

from rhythm_os.domain.oracle.phase import describe_alignment, summarize_convergence
from rhythm_os.psr.append_domain_wave import append_domain_wave
from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.runtime.bus import load_recent_domain_waves, today_bus_file


def emit_convergence_summary(
    *,
    bus_dir: Path,
    t_ref: float,
    history_window_sec: float,
    within_deg: float = 30.0,
) -> None:
    waves = load_recent_domain_waves(
        bus_dir=bus_dir,
        t_ref=t_ref,
        history_window_sec=history_window_sec,
    )
    if not waves:
        return

    descriptors = describe_alignment(
        t_ref=t_ref,
        domain_waves=waves,
        history_window_sec=history_window_sec,
    )
    if not descriptors:
        return  # silence valid

    summary = summarize_convergence(
        t_ref=t_ref,
        descriptors=descriptors,
        within_deg=within_deg,
    )

    code_map = {"none": 0.0, "low": 1.0, "moderate": 2.0, "high": 3.0}
    conv_code = float(code_map.get(summary.convergence, 0.0))

    dw_out = DomainWave(
        t=float(t_ref),
        domain="oracle",
        channel="convergence_summary",
        field_cycle="computed",
        phase_external=0.0,
        phase_field=0.0,
        phase_diff=conv_code,
        coherence=None,
        extractor={
            "cycle_id": compute_cycle_id(t_ref=t_ref, runner="run_cycle_once", version="v1"),
            "within_deg": str(summary.within_deg),
            "active": str(summary.active),
            "within_count": str(summary.within_count),
            "mean_coherence": str(summary.mean_coherence) if summary.mean_coherence is not None else "none",
            "convergence": str(summary.convergence),
            "note": str(summary.note),
            "method": "describe_alignment + summarize_convergence",
            "version": "v1",
        },
    )

    from rhythm_os.runtime.bus import has_emission_at_time

    if has_emission_at_time(
        bus_dir=bus_dir,
        t_ref=t_ref,
        domain="oracle",
        channel="convergence_summary",
    ):
        return
    append_domain_wave(today_bus_file(bus_dir=bus_dir, t_ref=t_ref), dw_out)
