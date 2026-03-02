"""
POSTURE: MEMORY (SCAR STORE)

Domain-specific record of high-pressure encounters.

A scar is created when the system meets a pattern at the forest edge (high
forest_proximity) or encounters an anomaly.  Each subsequent encounter
reinforces the scar's pressure.  Between cycles, pressure decays — the scar
fades unless continually reinforced.

The lighthouse reads scars to attenuate forest_proximity for patterns the
system has already survived, so the system stays alert without being re-scared
by familiar territory.  Novel patterns keep full proximity.

Posture rules:
- Read/write authority is limited to this module.
- Routing authority stays with the Dispatcher — scars inform the lighthouse
  annotation only; they never override a routing decision directly.
- Domain-specific.  No cross-domain bleed.
- Scars are keyed by (domain, pattern_key).  pattern_key = "{seasonal_band}:{channel}".
- Append-on-first-encounter, reinforce on repeat.
- Pressure decays per cycle (multiplicative).  Pruned when pressure < PRUNE_THRESHOLD.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from rhythm_os.runtime.paths import SCARS_DIR

# ---------------------------------------------------------------------------
# In-memory write-through cache
#
# Keyed by the absolute file path (SCARS_DIR / "{domain}.jsonl") so that:
#   - Production: constant SCARS_DIR means cache hits across calls in one process.
#   - Tests: monkeypatched SCARS_DIR produces a different path per test, giving
#     automatic isolation without any explicit cache clearing.
#
# The cache is write-through: _save_scars updates it before writing to disk,
# so subsequent _load_scars calls within the same process skip file I/O.
# ---------------------------------------------------------------------------

_scar_cache: dict = {}  # Dict[Path, Dict[str, Scar]]


# ---------------------------------------------------------------------------
# Pressure constants
# ---------------------------------------------------------------------------

DECAY_RATE_DEFAULT = 0.05  # 5 % pressure lost per reference cycle
PRUNE_THRESHOLD = 0.01  # prune scars below this pressure
MAX_PRESSURE = 2.0  # cap on accumulated pressure
MAX_ATTENUATION = 0.85  # maximum forest_proximity reduction
# (never fully suppress — stay alert, not blind)

# One decay "tick" = one hour of real elapsed time.
# Keeps decay semantics stable whether the system runs every second or once a day.
# pressure *= (1 - rate) ** (elapsed_seconds / _REFERENCE_CYCLE_SECONDS)
_REFERENCE_CYCLE_SECONDS: float = 3600.0


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class Scar:
    scar_id: str
    domain: str
    pattern_key: str  # "{seasonal_band}:{channel}"
    pressure: float  # [0, MAX_PRESSURE]
    changed: bool  # did THIS encounter alter system state?
    trigger: str  # "forest_proximity" | "anomaly" | "compound"
    first_seen: float  # unix timestamp
    last_reinforced: float  # unix timestamp
    decay_rate: float
    reinforcement_count: int
    ever_changed: bool = False  # has any encounter ever flagged a change?
    last_decayed: float = 0.0  # wall-clock time decay was last applied (0 = never)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Scar":
        return cls(**d)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pattern_key(seasonal_band: Optional[str], channel: str) -> str:
    """Fingerprint for a pattern: seasonal context + measurement channel."""
    band = seasonal_band or "unknown"
    return f"{band}:{channel}"


def _scar_id(domain: str, key: str) -> str:
    raw = f"{domain}:{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _domain_file(domain: str) -> Path:
    return SCARS_DIR / f"{domain}.jsonl"


def _load_scars(domain: str) -> Dict[str, Scar]:
    path = _domain_file(domain)
    if path in _scar_cache:
        return _scar_cache[path]
    scars: Dict[str, Scar] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    scar = Scar.from_dict(json.loads(line))
                    scars[scar.scar_id] = scar
                except Exception:
                    continue
    _scar_cache[path] = scars
    return scars


def _save_scars(domain: str, scars: Dict[str, Scar]) -> None:
    """Full rewrite of the domain scar file (scars are small — O(seasons × channels))."""
    path = _domain_file(domain)
    _scar_cache[path] = scars  # write-through: update cache before disk write
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for scar in scars.values():
            f.write(json.dumps(scar.to_dict()) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_scar(domain: str, key: str) -> Optional[Scar]:
    """Return the Scar for (domain, key), or None if no scar exists."""
    scars = _load_scars(domain)
    return scars.get(_scar_id(domain, key))


def get_attenuation(domain: str, key: str) -> float:
    """
    Return the scar attenuation factor for a pattern in a domain.

    0.0        → no scar; full forest_proximity retained (novel pattern).
    MAX_ATTENUATION → heavily scarred; proximity strongly reduced (familiar territory).

    The effective forest_proximity after attenuation:
        effective_fp = raw_fp * (1 - attenuation)
    """
    scar = get_scar(domain, key)
    if scar is None:
        return 0.0
    return min(scar.pressure / MAX_PRESSURE, MAX_ATTENUATION)


def _confidence_decay_rate(pattern_confidence: float) -> float:
    """
    Derive decay rate from seasonal pattern_confidence.

    Low confidence (uncertain season) → scars decay slowly — hold the memory.
    High confidence (stable season)   → scars decay at standard rate — trust current state.

        decay_rate = DECAY_RATE_DEFAULT * max(confidence, 0.2)

    Floor at 0.2 prevents zombie scars during deep-uncertainty periods.
    """
    return DECAY_RATE_DEFAULT * max(float(pattern_confidence), 0.2)


def write_scar(
    domain: str,
    key: str,
    pressure_delta: float,
    changed: bool,
    trigger: str,
    pattern_confidence: float = 1.0,
) -> Scar:
    """
    Create or reinforce a scar for (domain, key).

    On first encounter: creates scar with pressure = pressure_delta.
    On repeat: adds pressure_delta to existing pressure (capped at MAX_PRESSURE).
    """
    scars = _load_scars(domain)
    sid = _scar_id(domain, key)
    now = time.time()

    decay_rate = _confidence_decay_rate(pattern_confidence)

    if sid in scars:
        existing = scars[sid]
        scars[sid] = Scar(
            scar_id=sid,
            domain=domain,
            pattern_key=key,
            pressure=min(existing.pressure + pressure_delta, MAX_PRESSURE),
            changed=changed,  # current encounter only
            ever_changed=changed or existing.ever_changed,  # accumulated history
            trigger=trigger,
            first_seen=existing.first_seen,
            last_reinforced=now,
            last_decayed=now,  # reset baseline — pressure is accurate as of now
            decay_rate=decay_rate,
            reinforcement_count=existing.reinforcement_count + 1,
        )
    else:
        scars[sid] = Scar(
            scar_id=sid,
            domain=domain,
            pattern_key=key,
            pressure=min(pressure_delta, MAX_PRESSURE),
            changed=changed,
            ever_changed=changed,
            trigger=trigger,
            first_seen=now,
            last_reinforced=now,
            last_decayed=now,
            decay_rate=decay_rate,
            reinforcement_count=1,
        )

    _save_scars(domain, scars)
    return scars[sid]


def apply_decay(domain: str) -> int:
    """
    Apply time-proportional multiplicative decay to all scars in a domain.

    Pressure decays continuously based on wall-clock elapsed time since the last
    decay application (or since creation on first call).  The rate is calibrated
    in units of _REFERENCE_CYCLE_SECONDS (one hour), so decay semantics are stable
    whether the system runs every second or once a day.

    Formula: new_pressure = pressure * (1 - decay_rate) ** (elapsed_s / reference_s)

    Prunes scars whose pressure falls below PRUNE_THRESHOLD.
    Returns the number of scars pruned.
    """
    now = time.time()
    scars = _load_scars(domain)
    if not scars:
        return 0

    pruned = 0
    active: Dict[str, Scar] = {}

    for sid, scar in scars.items():
        # Elapsed time since last decay tick (fall back to last_reinforced for old scars)
        baseline = (
            scar.last_decayed if scar.last_decayed > 0.0 else scar.last_reinforced
        )
        elapsed_s = max(now - baseline, 0.0)
        elapsed_cycles = elapsed_s / _REFERENCE_CYCLE_SECONDS
        new_pressure = scar.pressure * (1.0 - scar.decay_rate) ** elapsed_cycles

        if new_pressure < PRUNE_THRESHOLD:
            pruned += 1
            continue
        active[sid] = Scar(
            scar_id=scar.scar_id,
            domain=scar.domain,
            pattern_key=scar.pattern_key,
            pressure=new_pressure,
            changed=scar.changed,
            ever_changed=scar.ever_changed,
            trigger=scar.trigger,
            first_seen=scar.first_seen,
            last_reinforced=scar.last_reinforced,
            last_decayed=now,
            decay_rate=scar.decay_rate,
            reinforcement_count=scar.reinforcement_count,
        )

    _save_scars(domain, active)
    return pruned


def apply_all_decay() -> Dict[str, int]:
    """
    Apply one cycle of decay to every domain scar file.
    Returns {domain: pruned_count} for all domains with active scars.
    """
    results: Dict[str, int] = {}
    if not SCARS_DIR.exists():
        return results
    for path in SCARS_DIR.glob("*.jsonl"):
        domain = path.stem
        results[domain] = apply_decay(domain)
    return results
