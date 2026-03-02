# rhythm_os/core/domain_clocks/cyber.py
"""
CYBER CLOCK STACK — FROZEN v1

Purpose:
- Define operational temporal bands for cyber cadence detection
- No interpretation
- No tuning
- No ML
- Pure time constants
"""

from typing import Dict

CYBER_CYCLES: Dict[str, float] = {
    # High-frequency burst detection
    "burst_250ms": 0.25,
    "burst_1s": 1.0,
    # Short cadence / retry / beacon rhythms
    "beat_5s": 5.0,
    # Common scan / cron periodicity
    "minute_60s": 60.0,
    # Slow-roll infiltration / drift
    "roll_15m": 900.0,
    # Session-level modulation
    "session_1h": 3600.0,
}
