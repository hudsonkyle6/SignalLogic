# oracle.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Literal, Any
import math


# ---------------------------------------------------------------------
# Vocabulary (descriptive only)
# ---------------------------------------------------------------------

Pattern = Literal[
    "noisy",
    "near_lock",
    "partial_alignment",
    "phase_lagging",
    "phase_leading",
]


# ---------------------------------------------------------------------
# Oracle Records (geometry only)
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class AlignmentDescriptor:
    """
    Oracle alignment descriptor.

    Geometry only.
    No posture.
    No authority.
    No decisions.
    """

    t: float
    field_cycle: str
    domain: str
    channel: str

    phase_diff_rad: float
    phase_diff_deg: float
    coherence_ext: Optional[float]

    pattern: Pattern


@dataclass(frozen=True)
class ConvergenceSummary:
    """
    Descriptive convergence summary.

    Reports spatial density only.
    No evaluation.
    No gating.
    """

    t: float
    active: int
    within_deg: float
    within_count: int
    mean_coherence: Optional[float]
    convergence: Literal["none", "low", "moderate", "high"]
    note: str


# ---------------------------------------------------------------------
# Internal helpers (geometry only)
# ---------------------------------------------------------------------


def _classify_pattern(delta_deg: float, coherence: Optional[float]) -> Pattern:
    """
    Fixed geometric partitions for phase topology.

    Thresholds are descriptive buckets only.
    No ordering, quality judgment, or authority.
    """

    abs_d = abs(delta_deg)

    if coherence is not None and coherence < 0.5:
        return "noisy"

    if abs_d <= 15.0:
        return "near_lock"

    if abs_d <= 60.0:
        return "partial_alignment"

    return "phase_lagging" if delta_deg < 0 else "phase_leading"


# ---------------------------------------------------------------------
# Functional Oracle (pure, stateless)
# ---------------------------------------------------------------------


def describe_alignment(
    *,
    t_ref: float,
    domain_waves: List[Any],
    history_window_sec: float,
) -> List[AlignmentDescriptor]:
    """
    Describe phase alignment geometry across domain waves.

    The history window defines representational scope only.
    Records outside the window are not invalidated.
    """

    out: List[AlignmentDescriptor] = []

    for dw in domain_waves:
        t = float(dw.t)

        if abs(t - t_ref) > history_window_sec:
            continue

        delta_rad = float(dw.phase_diff)
        delta_deg = math.degrees(delta_rad)

        coherence = dw.coherence
        coherence = float(coherence) if coherence is not None else None

        field_cycle = getattr(dw, "field_cycle", "unknown")

        out.append(
            AlignmentDescriptor(
                t=t,
                field_cycle=field_cycle,
                domain=dw.domain,
                channel=dw.channel,
                phase_diff_rad=delta_rad,
                phase_diff_deg=delta_deg,
                coherence_ext=coherence,
                pattern=_classify_pattern(delta_deg, coherence),
            )
        )

    return out


def summarize_convergence(
    *,
    t_ref: float,
    descriptors: List[AlignmentDescriptor],
    within_deg: float = 30.0,
) -> ConvergenceSummary:
    """
    Descriptive convergence summary.

    Convergence labels describe spatial density bands only.
    They do not imply strength, readiness, or permission.
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

    within_count = sum(1 for d in descriptors if abs(d.phase_diff_deg) <= within_deg)

    coherences = [d.coherence_ext for d in descriptors if d.coherence_ext is not None]
    mean_coh = (sum(coherences) / len(coherences)) if coherences else None

    frac = within_count / len(descriptors)

    # Fixed categorical density bands (descriptive only)
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
# Oracle domain wrapper (canonical boundary)
# ---------------------------------------------------------------------


class Oracle:
    """
    Oracle domain.

    Descriptive only.
    Configurable, never authoritative.
    """

    def __init__(self, *, history_window_hours: float = 24.0):
        self.history_window_sec = history_window_hours * 3600.0

    def describe(
        self,
        *,
        t_now: float,
        domain_waves: List[Any],
        field_waves: List[Any] | None = None,
    ) -> List[AlignmentDescriptor]:
        """
        Adapter-facing surface.

        Ignores non-oracle inputs (field_waves).
        """
        return describe_alignment(
            t_ref=t_now,
            domain_waves=domain_waves,
            history_window_sec=self.history_window_sec,
        )

    def summarize_convergence(
        self,
        *,
        t_ref: float,
        descriptors: List[AlignmentDescriptor],
        within_deg: float = 30.0,
    ) -> ConvergenceSummary:
        return summarize_convergence(
            t_ref=t_ref,
            descriptors=descriptors,
            within_deg=within_deg,
        )
