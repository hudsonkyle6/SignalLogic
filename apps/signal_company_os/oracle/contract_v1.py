# rhythm_os/oracle/contract_v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ----------------------------
# Version stamps (filled in Step 5, referenced now)
# ----------------------------
ORACLE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# ----------------------------
# Core required inputs for Oracle (per-day row in merged/journal)
# ----------------------------
# ----------------------------
# Required inputs by Oracle layer
# ----------------------------

REQUIRED_L1_COLUMNS = [
    "Date",
    "Season",
    "ResonanceValue",
    "Amplitude",
    "H_t",
    "GhostStabilityIndex",
    "WVI",
    "EnvFactor",
]

REQUIRED_L4_COLUMNS = [
    "Date",
    "Season",
    "ResonanceValue",
    "Amplitude",
    "H_t",
    "GhostStabilityIndex",
    "WVI",
    "EnvFactor",
    # L4 consumes upstream memory + phase if present,
    # but they are NOT hard requirements
]


# Columns that must never be NA for “today” (tighten over time)
NEVER_NULL_TODAY: List[str] = [
    "Date",
    "Season",
    "ResonanceValue",
    "Amplitude",
    "H_t",
    "GhostStabilityIndex",
    "WVI",
    "EnvFactor",
]

# Allowed NA today (explicitly tolerated; you can tighten later)
ALLOWED_NULL_TODAY: List[str] = [
    "EnvPressure",
    "G_t",
    "MemoryCharge",
    "Afterglow",
    "MemoryDrift",
    "MemoryPhaseCoherence",
    "phi_h",
    "phi_e",
    "HSTResDrift",
    "HSTPhaseDiv",
    "DarkFieldBand",
]

# Expected numeric normalization ranges (where applicable)
# (min, max) inclusive
# Normalized fields strictly in [0,1]
RANGES_0_1: Dict[str, Tuple[float, float]] = {
    "ResonanceValue": (0.0, 1.0),
    "Amplitude": (0.0, 1.0),
    "H_t": (0.0, 1.0),
    "GhostStabilityIndex": (0.0, 1.0),
    "WVI": (0.0, 1.0),
    "EnvFactor": (0.0, 1.0),
    "MemoryCharge": (0.0, 1.0),
    "Afterglow": (0.0, 1.0),
    "MemoryPhaseCoherence": (0.0, 1.0),
}

# Gain / amplification terms (non-negative, unbounded above)
RANGES_NON_NEGATIVE: Dict[str, Tuple[float, float]] = {
    "G_t": (0.0, float("inf")),
}


# Required outputs per oracle layer (written to oracle_layer*.csv and/or merged)
L1_OUTPUTS = ["OCI", "RiskIndex", "OracleBand", "OracleBias"]
L2_OUTPUTS = [
    "WorldField", "HumanField", "EnvField", "GhostField", "MemoryField",
    "HCFIndex", "AlignmentBand", "AlignmentBias"
]
L3_OUTPUTS = ["HorizonIndex", "HorizonBand", "HorizonBias", "ShortWindow", "LongWindow", "MacroState"]
L4_OUTPUTS = ["D_t", "DarkFieldBand", "D_HStab", "D_DriftStab", "D_MemoryField", "D_GhostField", "D_EnvField"]
