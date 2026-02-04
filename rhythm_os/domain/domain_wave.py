#domain_wave.py
from dataclasses import dataclass
from typing import Dict, Optional
import json

@dataclass(frozen=True)
class DomainWave:
    """
    Descriptive phase relationship between an external oscillator
    and the sovereign oscillatory field.
    """

    t: float                      # UTC timestamp (seconds)
    domain: str                   # e.g. "weather", "tides", "energy"
    channel: str                  # e.g. "temperature", "velocity"

    field_cycle: str              # ← REQUIRED (diurnal | semi_diurnal | seasonal | longwave)

    phase_external: float         # radians [0, 2π)
    phase_field: float            # radians [0, 2π)
    phase_diff: float             # wrapped radians [-π, π]

    coherence: Optional[float]    # |<exp(jΔϕ)>| or None

    extractor: Dict[str, str]     # method metadata only (no params)

    def to_dict(self) -> Dict:
        return {
            "t": self.t,
            "domain": self.domain,
            "channel": self.channel,
            "field_cycle": self.field_cycle,
            "phase_external": self.phase_external,
            "phase_field": self.phase_field,
            "phase_diff": self.phase_diff,
            "coherence": self.coherence,
            "extractor": self.extractor,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))
