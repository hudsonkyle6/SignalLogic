"""
Canonical helm engine — operational posture recommendation.

Derives a WAIT / PREPARE / ACT / PUSH recommendation from cycle signals.
This is the single source of truth; all callers (dashboard, cadence runner,
voice narrator) must import from here rather than re-implementing the logic.

Deterministic — no LLM, no side effects, no I/O.

States
------
WAIT    Adverse or high-pressure conditions.  Hold position, protect work.
PREPARE Conditions are shifting.  Set foundations, be ready to move.
ACT     Stable and favorable.  Execute planned work at normal pace.
PUSH    Rare optimal window.  Maximum disciplined effort.

Decision layers (first match wins)
-----------------------------------
1. Antifragile overrides  — brittleness / strain indices (if provided)
2. Routing stress         — anomaly rate, admission rate
3. Convergence pressure   — strong > weak > no convergence
4. Drift floor            — high drift caps the state to PREPARE
5. Clean-window detection — high admission + zero anomalies → PUSH
6. Default               → ACT
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Display constants — imported by dashboard and other UI layers
# ---------------------------------------------------------------------------

HELM_STYLES: dict[str, tuple[str, str]] = {
    "WAIT":    ("bold red",    "◼"),
    "PREPARE": ("bold yellow", "◆"),
    "ACT":     ("bold green",  "●"),
    "PUSH":    ("bold white",  "★"),
}

HELM_GUIDANCE: dict[str, str] = {
    "WAIT":    "Contract. Clear backlog. Protect position.",
    "PREPARE": "Align. Set foundations. Be ready to move.",
    "ACT":     "Move. Execute planned work. Normal output.",
    "PUSH":    "Rare window. Take the big swing — with discipline.",
}


# ---------------------------------------------------------------------------
# HelmResult — immutable output of compute_helm()
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HelmResult:
    """Immutable helm recommendation derived from one cycle's signals."""

    state: str           # WAIT | PREPARE | ACT | PUSH
    rationale: str       # one-line human-readable reason
    ts: float            # unix timestamp when computed

    # Driving metrics — stored for retrospective trust scoring
    admission_rate: float = 0.0
    anomaly_rate:   float = 0.0
    strong_events:  int   = 0
    event_count:    int   = 0
    brittleness:    float = 0.0
    strain:         float = 0.0

    @property
    def guidance(self) -> str:
        """Plain-language action guidance for the current state."""
        return HELM_GUIDANCE.get(self.state, "")

    @property
    def style(self) -> tuple[str, str]:
        """(rich_style, icon) pair for terminal rendering."""
        return HELM_STYLES.get(self.state, ("dim", "·"))

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# compute_helm — main entry point
# ---------------------------------------------------------------------------

def compute_helm(
    cycle_result: Any,
    *,
    antifragile: Optional[dict] = None,
) -> HelmResult:
    """
    Derive a helm recommendation from cycle signals.

    Parameters
    ----------
    cycle_result : CycleResult (or any object with the expected attributes),
                   or None — returns PREPARE / awaiting baseline.
    antifragile  : Optional dict with keys:
                     brittleness_index [0, 1]  — fragility of current state
                     strain_index      [0, 1]  — load pressure
                     drift_index       [0, 1]  — deviation from baseline
                   When None, antifragile overrides and the drift floor are
                   skipped entirely.

    Returns
    -------
    HelmResult (frozen dataclass)
    """
    now = time.time()

    if cycle_result is None:
        return HelmResult(
            state="PREPARE",
            rationale="awaiting first full cycle — establish baseline",
            ts=now,
        )

    cs = getattr(cycle_result, "convergence_summary", None) or {}
    drained    = getattr(cycle_result, "packets_drained",       0) or 1
    committed  = getattr(cycle_result, "committed",              0)
    quarantined = getattr(cycle_result, "spillway_quarantined",  0)

    strong      = cs.get("strong_events",          0)
    event_count = cs.get("convergence_event_count", 0)
    events      = cs.get("convergence_events",      [])

    adm_rate  = committed  / drained
    anom_rate = quarantined / drained

    # Antifragile indices (all default to 0 when not provided)
    brittleness = 0.0
    strain      = 0.0
    drift       = 0.0
    if antifragile:
        brittleness = float(antifragile.get("brittleness_index", 0.0))
        strain      = float(antifragile.get("strain_index",      0.0))
        drift       = float(antifragile.get("drift_index",       0.0))

    def _result(state: str, rationale: str) -> HelmResult:
        return HelmResult(
            state=state,
            rationale=rationale,
            ts=now,
            admission_rate=adm_rate,
            anomaly_rate=anom_rate,
            strong_events=strong,
            event_count=event_count,
            brittleness=brittleness,
            strain=strain,
        )

    # ------------------------------------------------------------------
    # Layer 1: Antifragile overrides
    # ------------------------------------------------------------------
    if brittleness > 0.7:
        return _result(
            "WAIT",
            f"high brittleness ({brittleness:.2f}) — system too fragile to commit",
        )
    if strain > 0.8:
        return _result(
            "WAIT",
            f"high strain ({strain:.2f}) — system under excessive load",
        )

    # ------------------------------------------------------------------
    # Layer 2: Routing stress
    # ------------------------------------------------------------------
    if anom_rate > 0.10:
        return _result(
            "WAIT",
            f"elevated anomalies ({quarantined} quarantined, {anom_rate:.0%})"
            " — investigate before committing",
        )
    if adm_rate < 0.50:
        return _result(
            "WAIT",
            f"low admission rate ({adm_rate:.0%}) — routing under pressure",
        )

    # Drift floor: high deviation caps ACT/PUSH → PREPARE
    _drift_floor = drift > 0.6

    # ------------------------------------------------------------------
    # Layer 3: Convergence pressure
    # ------------------------------------------------------------------
    if strong > 0:
        ev0    = next((e for e in events if e.get("strength") == "strong"), {})
        doms   = " + ".join(sorted(ev0.get("domains", [])))
        reason = (
            f"{doms} converging at strong alignment — conditions in flux, hold position"
            if doms else
            "strong cross-domain convergence — hold position"
        )
        return _result("WAIT", reason)

    if event_count > 0:
        ev0  = events[0] if events else {}
        doms = " + ".join(sorted(ev0.get("domains", [])))
        reason = (
            f"{doms} beginning to align — conditions shifting, set your stance"
            if doms else
            "domains beginning to align — conditions shifting"
        )
        return _result("PREPARE", reason)

    # ------------------------------------------------------------------
    # Layer 4: Drift floor
    # ------------------------------------------------------------------
    if _drift_floor:
        return _result(
            "PREPARE",
            f"high drift ({drift:.2f}) — conditions deviating from baseline,"
            " align before committing",
        )

    # ------------------------------------------------------------------
    # Layer 5: Clean-window detection
    # ------------------------------------------------------------------
    if adm_rate > 0.88 and quarantined == 0:
        return _result(
            "PUSH",
            f"all domains clear, clean routing ({adm_rate:.0%} admitted)"
            " — favorable window",
        )

    # ------------------------------------------------------------------
    # Layer 6: Default — stable, nominal
    # ------------------------------------------------------------------
    return _result(
        "ACT",
        f"stable conditions, nominal routing ({adm_rate:.0%} admitted)",
    )
