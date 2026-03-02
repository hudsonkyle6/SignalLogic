# rhythm_os/domain/oracle/descriptors.py

from dataclasses import dataclass
from typing import Literal

AlignmentPattern = Literal[
    "none",
    "near_lock",
    "partial_alignment",
    "divergent",
]


@dataclass(frozen=True)
class AlignmentDescriptor:
    """
    Descriptive-only oracle record.

    No authority.
    No thresholds.
    No decisions.
    """

    t: float
    field_cycle: str  # diurnal | semi_diurnal | seasonal | longwave
    domain: str
    channel: str

    phase_diff_rad: float
    phase_diff_deg: float

    coherence_ext: float

    pattern: AlignmentPattern
