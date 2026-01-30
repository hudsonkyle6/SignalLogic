"""
Antifragile Engine™ — Human Signal Layer for Rhythm OS

This package holds the human-facing side of the system:

- ledger.py            : daily human log (BodyLoad, Clarity, Resistance, etc.)
- tide_engine.py       : environmental / seasonal pressure (Tide Index)
- weekly_signatures.py : weekly pattern aggregation
- compass.py           : daily decision engine (WAIT / PREPARE / ACT / PUSH)
- pattern_alignment.py : merged dataset (world + human + tide) for ML

Typical flow:

  1) Run Rhythm OS kernel to update signal_journal.csv
  2) python -m rhythm_os.antifragile.ledger
  3) python -m rhythm_os.antifragile.tide_engine
  4) python -m rhythm_os.antifragile.compass
  5) (weekly) python -m rhythm_os.antifragile.weekly_signatures
  6) (periodic) python -m rhythm_os.antifragile.pattern_alignment

This forms the human-pattern half of the Trinity:
Rhythm OS (world) ↔ Antifragile Engine (human) ↔ Lighthouse ML.
"""

from .ledger import log_today_entry
from .tide_engine import run_tide_engine
from .compass import run_compass
from .weekly_signatures import build_weekly_signatures
from .pattern_alignment import build_pattern_alignment

__all__ = [
    "log_today_entry",
    "run_tide_engine",
    "run_compass",
    "build_weekly_signatures",
    "build_pattern_alignment",
]
