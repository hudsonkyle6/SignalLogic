"""
Wave → WaveView Adapter

READ-ONLY.
NO COMPUTATION.
NO INTERPRETATION.

This adapter exists solely to present sealed Wave objects
to the signal_scope without expanding authority.
"""

from __future__ import annotations
from typing import Optional
from rhythm_os.ui.signal_scope import WaveView


class WaveViewAdapter:
    def __init__(self, wave: object):
        self._wave = wave

    @property
    def t(self) -> float:
        return getattr(self._wave, "t")

    @property
    def coherence(self) -> float:
        return getattr(self._wave, "coherence")

    @property
    def phase_spread(self) -> float:
        return getattr(self._wave, "phase_spread")

    @property
    def buffer_margin(self) -> float:
        return getattr(self._wave, "buffer_margin")

    @property
    def persistence(self) -> int:
        return getattr(self._wave, "persistence")

    @property
    def drift(self) -> Optional[float]:
        return getattr(self._wave, "drift", None)

    @property
    def afterglow(self) -> Optional[float]:
        return getattr(self._wave, "afterglow", None)
