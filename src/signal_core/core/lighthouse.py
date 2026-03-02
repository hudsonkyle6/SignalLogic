"""
POSTURE: TRIBUTARY
Hypothesis-only. Must not write to Penstock.
See rhythm_os/TWO_WATERS.md

Two responsibilities:

1. annotate_packet() — PRE-GATE seasonal annotation.
   Reads seasonal_prior for the packet's timestamp and stamps the packet
   with seasonal_band, pattern_confidence, forest_proximity, and afterglow_decay.
   The gate ignores these fields entirely (purely structural).
   The dispatcher uses forest_proximity to orient routing.

2. illuminate() — POST-DISPATCH structural labeling.
   Non-authoritative summary of what was observed and where it was routed.
   No truth claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from .hydro_types import HydroPacket, DispatchDecision
from rhythm_os.runtime.seasonal_prior import compute_seasonal_prior
from rhythm_os.core.memory.scar import get_scar, pattern_key as _pattern_key

# Minimum pattern_confidence regardless of what the seasonal prior returns.
# Without this floor, a near-zero upstream confidence would cause scars to
# accumulate pressure they can never shed (decay_rate → 0), eventually
# blinding the system to familiar patterns at the worst possible moment.
_MIN_PATTERN_CONFIDENCE = 0.15

# Attenuation reduction factors when a scar's history flags are set.
# Applied multiplicatively on top of the confidence-weighted base attenuation.
#
# ever_changed=True: pattern has previously triggered action — stay more alert
#   even as it becomes familiar.  35% reduction in attenuation.
# changed=True (implies ever_changed): the last encounter also triggered action.
#   Additional 20% reduction — recent significance on top of historical.
#
# Combined floor: a scar with both flags active attenuates at 0.65 × 0.80 = 52%
# of what pressure alone would suggest.  Novel patterns (no scar) are unaffected.
_HISTORY_FACTOR_EVER_CHANGED = 0.65
_HISTORY_FACTOR_RECENTLY_CHANGED = 0.80


# ---------------------------------------------------------------------------
# Pre-gate annotation
# ---------------------------------------------------------------------------


def annotate_packet(packet: HydroPacket) -> HydroPacket:
    """
    Stamp seasonal Lighthouse annotations onto the packet BEFORE the gate.

    Returns a NEW (frozen) HydroPacket with seasonal context fields filled.
    If annotation fails for any reason, returns the original packet unchanged
    (fail-open — the gate must still decide structurally).

    POSTURE: TRIBUTARY — no authority, no persistence, no side effects.
    """
    if packet.seasonal_band is not None:
        # Already annotated (e.g. re-processed replay packet)
        return packet

    try:
        prior = compute_seasonal_prior(float(packet.t))
    except Exception:
        return packet  # fail-open: seasonal context is informational only

    confidence = max(float(prior.pattern_confidence), _MIN_PATTERN_CONFIDENCE)

    return HydroPacket(
        **{
            **packet.__dict__,
            "seasonal_band": prior.seasonal_band,
            "pattern_confidence": confidence,
            "forest_proximity": prior.forest_proximity,
            "afterglow_decay": prior.afterglow_decay,
        }
    )


# ---------------------------------------------------------------------------
# Scar-based attenuation
# ---------------------------------------------------------------------------


def attenuate_with_scars(packet: HydroPacket) -> HydroPacket:
    """
    Reduce forest_proximity for patterns the system has already survived.

    Reads the scar store (domain-specific, read-only from this posture) and
    applies a pressure-weighted attenuation to forest_proximity.  Novel
    patterns are unaffected.  Familiar territory carries less weight each
    time the system encounters it without being destabilised.

    POSTURE: TRIBUTARY — read-only.  Scars are written by Hydro, not Lighthouse.
    """
    if packet.forest_proximity is None:
        return packet

    try:
        key = _pattern_key(packet.seasonal_band, packet.channel)
        scar = get_scar(packet.domain, key)
    except Exception:
        return packet  # fail-open — scar read is informational only

    if scar is None:
        return packet  # novel pattern — no attenuation

    raw_attenuation = min(
        scar.pressure / 2.0, 0.85
    )  # mirrors MAX_PRESSURE / MAX_ATTENUATION

    # Scale by seasonal confidence.
    # High confidence: trust the scar memory — full attenuation.
    # Low confidence (transition): stay alert on familiar patterns — reduced attenuation.
    confidence = (
        float(packet.pattern_confidence)
        if packet.pattern_confidence is not None
        else 1.0
    )

    # Scale by change history.
    # ever_changed: this pattern has previously triggered action — hold back some
    #   attenuation so the system doesn't go fully quiet on dangerous territory.
    # changed (last encounter also triggered): recent significance compounds the wariness.
    history_factor = 1.0
    if scar.ever_changed:
        history_factor *= _HISTORY_FACTOR_EVER_CHANGED
    if scar.changed:
        history_factor *= _HISTORY_FACTOR_RECENTLY_CHANGED

    effective_attenuation = raw_attenuation * confidence * history_factor

    return HydroPacket(
        **{
            **packet.__dict__,
            "forest_proximity": packet.forest_proximity * (1.0 - effective_attenuation),
        }
    )


# ---------------------------------------------------------------------------
# Post-dispatch illumination
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LighthouseSummary:
    packet_id: str
    route: str
    pressure_class: str
    note: str
    hypothesis: bool
    features: Dict[str, Any]


def illuminate(packet: HydroPacket, decision: DispatchDecision) -> LighthouseSummary:
    """
    Non-authoritative illumination only.
    No truth claims.
    """
    features: Dict[str, Any] = {
        "lane": packet.lane,
        "domain": packet.domain,
        "channel": packet.channel,
        "rate": packet.rate,
        "anomaly_flag": packet.anomaly_flag,
        "replay": packet.replay,
    }

    # No interpretation of meaning; only structural/contextual labeling.
    note = "observation"
    hypothesis = False

    if decision.route.value == "TURBINE":
        note = "exploratory basin (non-production)"
        hypothesis = True

    if decision.route.value == "SPILLWAY":
        note = "pressure relief path (operational)"
        hypothesis = True

    return LighthouseSummary(
        packet_id=packet.packet_id,
        route=decision.route.value,
        pressure_class=decision.pressure_class,
        note=note,
        hypothesis=hypothesis,
        features=features,
    )
