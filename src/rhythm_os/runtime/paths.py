"""
Canonical data path constants for rhythm_os.

All paths are absolute and resolved at import time.

Override the data root with the SIGNALLOGIC_DATA environment variable so the
system can store its data outside the package tree (required for containers,
read-only installs, and multi-instance deployments).

    export SIGNALLOGIC_DATA=/var/lib/signallogic   # system-wide
    export SIGNALLOGIC_DATA=/data                  # inside a Docker container

When SIGNALLOGIC_DATA is not set the default falls back to the legacy location
inside the installed package (src/rhythm_os/data) so existing dev installs
continue to work without any config change.

Usage:
    from rhythm_os.runtime.paths import TURBINE_DIR, QUEUE_PATH, BUS_DIR
"""

from __future__ import annotations

import os
from pathlib import Path

# Prefer an explicit external data root so the package tree stays read-only.
_DATA_ENV = os.environ.get("SIGNALLOGIC_DATA", "").strip()
if _DATA_ENV:
    DATA_DIR = Path(_DATA_ENV)
else:
    # Legacy default: data lives beside the package source
    _PKG_ROOT = Path(__file__).resolve().parents[1]  # src/rhythm_os/
    DATA_DIR = _PKG_ROOT / "data"

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

# Scar store — domain-specific pressure memory (one JSONL per domain)
SCARS_DIR = DATA_DIR / "scars"

# Control signal channel — real-time dispatch decisions for downstream consumers
# Daily rotation: signals-YYYY-MM-DD.jsonl written inside this directory.
CONTROL_DIR = DATA_DIR / "dark_field" / "control"

# Domain wave bus — DomainWave JSONL written by PSR emitters (one file per day)
DOMAIN_DIR = DATA_DIR / "dark_field" / "domain"

# Raw market observations — written by observatory tools before PSR projection
MARKET_RAW_DIR = DATA_DIR / "dark_field" / "market_raw"

# Human trafficking signal observations (stub — awaiting data feed partnership)
HUMAN_TRAFFICKING_DIR = DATA_DIR / "dark_field" / "human_trafficking"

# Hydro audit log — append-only record of every gate decision
AUDIT_PATH = DATA_DIR / "dark_field" / "hydro" / "audit.jsonl"

# PSR intermediate store (pre-domain aggregates, not primary dark field)
PSR_DIR = DATA_DIR / "psr"

# Gate registry — open/close events, append-only JSONL audit log
GATES_DIR = DATA_DIR / "dark_field" / "gates"

# Turbine action log — proposed and resolved TurbineAction records
GATE_ACTIONS_DIR = DATA_DIR / "dark_field" / "gate_actions"

# Convergence memory — cross-day domain-pair × phase-bucket observations
CONVERGENCE_MEMORY_PATH = DATA_DIR / "dark_field" / "convergence" / "memory.jsonl"
