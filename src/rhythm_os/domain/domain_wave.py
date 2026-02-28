# Canonical definition lives in rhythm_os.psr.domain_wave.
# This re-export keeps existing imports working without duplication.
from rhythm_os.psr.domain_wave import DomainWave  # noqa: F401

__all__ = ["DomainWave"]
