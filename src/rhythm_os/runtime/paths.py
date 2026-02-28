"""
Canonical data path constants for rhythm_os.

All paths are absolute, resolved at import time relative to this file's
location — independent of the working directory when the process runs.

Usage:
    from rhythm_os.runtime.paths import TURBINE_DIR, QUEUE_PATH, BUS_DIR
"""
from __future__ import annotations

from pathlib import Path

# src/rhythm_os/
_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = _ROOT / "data"

# Penstock — sealed Waves (append-only ledger)
PENSTOCK_DIR = DATA_DIR / "dark_field" / "penstock"

# Turbine basin — exploratory observations (NOT penstock)
TURBINE_DIR = DATA_DIR / "dark_field" / "turbine"

# Hydro ingress queue (single-writer / single-drainer)
QUEUE_PATH = DATA_DIR / "dark_field" / "hydro" / "ingress.jsonl"

# PSR domain wave bus (DomainWave JSONL, read by oracle/antifragile emitters)
BUS_DIR = DATA_DIR / "bus"

# Natural Dark Field (raw natural-lane records for PSR projection)
NATURAL_DIR = DATA_DIR / "dark_field" / "natural"

# System meter records (hydro_meter output — one file per day, append-only)
METERS_DIR = DATA_DIR / "dark_field" / "meters"

# Mandates (human governance files, JSON)
MANDATES_DIR = DATA_DIR / "mandates"
