"""
POSTURE: TURBINE (EXPLORATORY BASIN)

Receives packets routed to the TURBINE channel.

Authority:
  - DOES observe cross-domain phase patterns
  - DOES append observations to turbine basin (NOT penstock)
  - DOES NOT commit to penstock
  - DOES NOT mutate packets
  - DOES NOT make execution decisions

The Turbine detects emergent phase convergence — moments where signals
from multiple domains cluster at the same position in the anchor cycles.
This is an observatory, not a decision engine.

Convergence across domains at the same diurnal phase is a signal.
The strength of that signal increases with the number of aligned domains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from .hydro_types import HydroPacket
from rhythm_os.runtime.temporal_anchor import compute_anchor, TemporalAnchor
from rhythm_os.runtime.paths import TURBINE_DIR

# Phase convergence window: how close two phases must be to count as aligned.
# 0.083 = 1 hour within a 12h semi-diurnal cycle (1/12 of the cycle).
CONVERGENCE_WINDOW = 0.083


# ------------------------------------------------------------
# Observation record
# ------------------------------------------------------------


@dataclass(frozen=True)
class TurbineObservation:
    """
    A single turbine observation. Records what was seen, not what was decided.
    """

    t: float
    packet_id: str
    domain: str
    lane: str
    route_reason: str  # D3_TURBINE_EXPLORATORY or D4_SAFE_FALLBACK
    diurnal_phase: float
    semi_diurnal_phase: float
    long_wave_phase: float
    dominant_hz: float
    aligned_domains: List[str]  # other domains sharing this phase window
    convergence_note: str  # human-readable pattern summary


# ------------------------------------------------------------
# Phase geometry
# ------------------------------------------------------------


def _circular_distance(a: float, b: float) -> float:
    """
    Shortest arc between two phases in [0, 1].
    Returns a value in [0, 0.5].
    """
    d = abs(a - b)
    return min(d, 1.0 - d)


# ------------------------------------------------------------
# History I/O
# ------------------------------------------------------------


def _load_recent_turbine(*, max_records: int = 100) -> List[dict]:
    """
    Load recent turbine observations for convergence comparison.
    Read-only. Best-effort. Malformed lines are skipped.
    """
    out: List[dict] = []
    if not TURBINE_DIR.exists():
        return out

    for f in sorted(TURBINE_DIR.glob("*.jsonl"), reverse=True):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
                if len(out) >= max_records:
                    return out
        except Exception:
            continue

    return out


def _append_observation(obs: TurbineObservation) -> None:
    """
    Append a turbine observation to the daily basin file.
    Append-only. No overwrite. No reads.
    """
    TURBINE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    path = TURBINE_DIR / f"{today}.jsonl"

    record = {
        "t": obs.t,
        "packet_id": obs.packet_id,
        "domain": obs.domain,
        "lane": obs.lane,
        "route_reason": obs.route_reason,
        "diurnal_phase": obs.diurnal_phase,
        "semi_diurnal_phase": obs.semi_diurnal_phase,
        "long_wave_phase": obs.long_wave_phase,
        "dominant_hz": obs.dominant_hz,
        "aligned_domains": obs.aligned_domains,
        "convergence_note": obs.convergence_note,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


# ------------------------------------------------------------
# Convergence assessment
# ------------------------------------------------------------


def _assess_convergence(
    anchor: TemporalAnchor,
    current_domain: str,
    history: List[dict],
) -> tuple[List[str], str]:
    """
    Find which OTHER domains have recent turbine packets within the
    convergence window of the current packet's diurnal phase.

    Cross-domain convergence (e.g. natural + system at the same phase)
    is a stronger signal than same-domain clustering.

    Returns (aligned_domains, note_string).
    """
    if not history:
        return [], "no_history"

    # Group most-recent observation per domain (excluding current domain)
    latest_by_domain: dict[str, dict] = {}
    for h in history:
        d = h.get("domain", "unknown")
        if d == current_domain:
            continue
        if d not in latest_by_domain:
            latest_by_domain[d] = h

    aligned_domains: List[str] = []
    for domain, rec in latest_by_domain.items():
        try:
            rec_phase = float(rec["diurnal_phase"])
        except (KeyError, TypeError, ValueError):
            continue
        if _circular_distance(anchor.diurnal_phase, rec_phase) <= CONVERGENCE_WINDOW:
            aligned_domains.append(domain)

    aligned_domains.sort()

    if not aligned_domains:
        return [], "isolated"

    if len(aligned_domains) == 1:
        note = f"weak:{aligned_domains[0]}"
    else:
        note = f"convergence:{','.join(aligned_domains)}"

    return aligned_domains, note


# ------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------


def process_turbine(packet: HydroPacket, route_reason: str) -> TurbineObservation:
    """
    Process a TURBINE-routed packet.

    1. Compute (or recover) temporal anchor from packet timestamp.
    2. Load recent turbine history.
    3. Assess phase convergence across domains.
    4. Append observation to turbine basin.
    5. Return observation (no side effects beyond the append).
    """
    # Prefer anchor phases already stamped on the packet by the throat;
    # fall back to computing from the raw timestamp.
    if (
        packet.diurnal_phase is not None
        and packet.semi_diurnal_phase is not None
        and packet.long_wave_phase is not None
    ):
        anchor = TemporalAnchor(
            t=float(packet.t),
            diurnal_phase=packet.diurnal_phase,
            semi_diurnal_phase=packet.semi_diurnal_phase,
            long_wave_phase=packet.long_wave_phase,
            dominant_hz=compute_anchor(
                float(packet.t), domain=packet.domain
            ).dominant_hz,
        )
    else:
        anchor = compute_anchor(float(packet.t), domain=packet.domain)

    history = _load_recent_turbine()
    aligned_domains, convergence_note = _assess_convergence(
        anchor, packet.domain, history
    )

    obs = TurbineObservation(
        t=float(packet.t),
        packet_id=packet.packet_id,
        domain=packet.domain,
        lane=packet.lane,
        route_reason=route_reason,
        diurnal_phase=anchor.diurnal_phase,
        semi_diurnal_phase=anchor.semi_diurnal_phase,
        long_wave_phase=anchor.long_wave_phase,
        dominant_hz=anchor.dominant_hz,
        aligned_domains=aligned_domains,
        convergence_note=convergence_note,
    )

    _append_observation(obs)
    return obs
