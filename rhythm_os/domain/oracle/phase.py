from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import math

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.domain.oracle.descriptors import (
    AlignmentDescriptor,
    AlignmentPattern,
)


# ---------------------------------------------------------------------
# Pattern classification (geometry only)
# ---------------------------------------------------------------------

# Fixed geometric partitions for phase topology.
# Thresholds are descriptive buckets only:
# - no ordering
# - no quality judgment
# - no decision authority
# Labels are topological descriptors, not evaluative signals.
def _classify_pattern(
    delta_deg: float,
    coherence: Optional[float],
) -> AlignmentPattern:
    """
    Classification returns topological descriptors of phase relationship.

    Buckets are fixed geometric partitions — not quality assessments.
    Coherence is used only to mark signal instability
    (low coherence → descriptive 'noisy' bucket),
    not dominance, readiness, or priority.
    """
    abs_d = abs(delta_deg)

    if coherence is not None and coherence < 0.5:
        return "none"

    if abs_d <= 15.0:
        return "near_lock"

    if abs_d <= 60.0:
        return "partial_alignment"

    return "divergent"


# ---------------------------------------------------------------------
# Oracle: Alignment description
# ---------------------------------------------------------------------

def describe_alignment(
    *,
    t_ref: float,
    domain_waves: List[DomainWave],
    history_window_sec: float = 24.0 * 3600.0,
) -> List[AlignmentDescriptor]:
    """
    Produce Oracle alignment descriptors from DomainWave records.

    DomainWave is assumed to already contain:
        - t
        - field_cycle
        - domain
        - channel
        - phase_diff   (radians, wrapped)
        - coherence    (optional)

    The history window defines the representational scope of the description.
    Records outside this window are excluded from this summary only —
    they are not rejected, invalidated, or deemed irrelevant elsewhere.

    Oracle:
        - does not read raw externals
        - does not compute posture
        - does not decide
    """
    out: List[AlignmentDescriptor] = []

    for dw in domain_waves:
        t = float(dw.t)
        if abs(t - t_ref) > history_window_sec:
            continue

        delta_rad = float(dw.phase_diff)
        delta_deg = math.degrees(delta_rad)

        coherence = dw.coherence
        pattern = _classify_pattern(delta_deg, coherence)

        out.append(
            AlignmentDescriptor(
                t=t,
                field_cycle=dw.field_cycle,
                domain=dw.domain,
                channel=dw.channel,
                phase_diff_rad=delta_rad,
                phase_diff_deg=delta_deg,
                coherence_ext=coherence,
                pattern=pattern,
            )
        )

    return out


# ---------------------------------------------------------------------
# Oracle: Convergence summary (descriptive only)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ConvergenceSummary:
    """
    Descriptive convergence summary.

    Reports the distribution of alignment descriptors within a fixed
    angular window.

    Performs no evaluation, no prioritization, no gating, and no decision.

    Convergence labels ("none", "low", "moderate", "high") are categorical
    descriptors of spatial density within the window — not quality,
    confidence, readiness, or strength signals.

    Thresholds are fixed density partitions — not tunable, not evaluative.
    """

    t: float
    active: int
    within_deg: float
    within_count: int
    mean_coherence: Optional[float]
    convergence: str
    note: str


def summarize_convergence(
    *,
    t_ref: float,
    descriptors: List[AlignmentDescriptor],
    within_deg: float = 30.0,
) -> ConvergenceSummary:
    """
    Pure descriptive convergence reporting.
    """
    if not descriptors:
        return ConvergenceSummary(
            t=t_ref,
            active=0,
            within_deg=within_deg,
            within_count=0,
            mean_coherence=None,
            convergence="none",
            note="no descriptors",
        )

    within_count = sum(
        1 for d in descriptors if abs(d.phase_diff_deg) <= within_deg
    )

    coherences = [
        d.coherence_ext for d in descriptors if d.coherence_ext is not None
    ]
    mean_coh = (sum(coherences) / len(coherences)) if coherences else None

    frac = within_count / len(descriptors)

    # Fixed categorical density buckets — descriptive only.
    # Labels are not ordered signals, quality ratings,
    # or authority-conferring indicators.
    if frac >= 0.7:
        level = "high"
    elif frac >= 0.4:
        level = "moderate"
    else:
        level = "low"

    return ConvergenceSummary(
        t=t_ref,
        active=len(descriptors),
        within_deg=within_deg,
        within_count=within_count,
        mean_coherence=mean_coh,
        convergence=level,
        note=f"{within_count}/{len(descriptors)} within ±{within_deg:.0f}°",
    )


# ---------------------------------------------------------------------
# Legacy stub preserved (inert)
# ---------------------------------------------------------------------

def recognize_phase(*, inputs: object | None = None):
    """
    Legacy placeholder kept for compatibility.

    Oracle vNext uses:
        - describe_alignment()
        - summarize_convergence()
    """
    return None

