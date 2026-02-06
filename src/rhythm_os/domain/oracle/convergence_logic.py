#convergence_logic.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, List, Dict
import statistics

from rhythm_os.domain.oracle.descriptors import AlignmentDescriptor


ConvergenceLevel = Literal[
    "none",
    "low",
    "moderate",
    "high",
]


@dataclass(frozen=True)
class CycleConvergenceSummary:
    """
    Oracle-level convergence description.

    Descriptive only.
    No authority.
    No posture.

    Convergence levels describe spatial density bands within the aggregated
    cycle window only. They do not imply signal strength, confidence,
    permission, readiness, or progression.
    """

    t: float
    field_cycle: str
    active_channels: int
    within_deg: float
    within_count: int
    mean_coherence: float
    convergence: ConvergenceLevel
    note: str


class OracleConvergence:
    """
    Aggregates AlignmentDescriptors to report cycle-local spatial density.

    This class performs descriptive aggregation only.
    Plurality thresholds define representational scope,
    not sufficiency, readiness, permission, or gating.
    """

    def __init__(
        self,
        *,
        within_deg: float = 30.0,
        min_channels: int = 3,
    ):
        self.within_deg = within_deg
        self.min_channels = min_channels

    def summarize(
        self,
        *,
        t_now: float,
        descriptors: List[AlignmentDescriptor],
    ) -> List[CycleConvergenceSummary]:
        summaries: List[CycleConvergenceSummary] = []

        # Group descriptors by sovereign field cycle
        by_cycle: Dict[str, List[AlignmentDescriptor]] = {}
        for d in descriptors:
            by_cycle.setdefault(d.field_cycle, []).append(d)

        for cycle, group in by_cycle.items():
            active = len(group)

            # Plurality threshold defines reporting scope only.
            # It does not invalidate descriptors, imply insufficiency,
            # or confer any authority/gating.
            if active < self.min_channels:
                summaries.append(
                    CycleConvergenceSummary(
                        t=t_now,
                        field_cycle=cycle,
                        active_channels=active,
                        within_deg=self.within_deg,
                        within_count=0,
                        mean_coherence=0.0,
                        convergence="none",
                        note=f"{active}/{self.min_channels} channels — below representational scope",
                    )
                )
                continue

            phases = [abs(d.phase_diff_deg) for d in group]
            coherences = [d.coherence_ext for d in group if d.coherence_ext is not None]

            within_count = sum(1 for p in phases if p <= self.within_deg)

            # mean_coherence is a descriptive statistic of coherence distribution only,
            # not a confidence, quality, or readiness measure.
            mean_coh = statistics.mean(coherences) if coherences else 0.0

            ratio = within_count / active

            # Fixed categorical density bands — descriptive only.
            # Labels are not ordered signals, priorities, quality ratings,
            # or readiness indicators. They confer no authority.
            if ratio >= 0.75:
                level: ConvergenceLevel = "high"
            elif ratio >= 0.5:
                level = "moderate"
            else:
                level = "low"

            summaries.append(
                CycleConvergenceSummary(
                    t=t_now,
                    field_cycle=cycle,
                    active_channels=active,
                    within_deg=self.within_deg,
                    within_count=within_count,
                    mean_coherence=mean_coh,
                    convergence=level,
                    note=f"{within_count}/{active} within ±{self.within_deg}°",
                )
            )

        return summaries
