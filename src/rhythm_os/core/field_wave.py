# rhythm_os/core/field_wave.py
from dataclasses import dataclass
from typing import Literal

FieldCycleName = Literal[
    "diurnal",
    "semi_diurnal",
    "seasonal",
    "longwave",
]


@dataclass(frozen=True)
class FieldWave:
    """
    Sovereign reference wave.
    Deterministic, physics-only, non-observational.
    """

    t: float
    cycle: FieldCycleName
    phase: float  # radians
    sine: float
    phasor: complex
