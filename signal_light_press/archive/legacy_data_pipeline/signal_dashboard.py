"""
Signal Dashboard — Canonical Diagnostic Instrument

PRESENTATION ONLY.
Passive oscilloscope for Rhythm OS.

FORBIDDEN:
- File I/O
- Signal computation
- Oracle logic
- Sage logic
- Shepherd logic
- Thresholding
- Decisions

ALLOWED:
- Rendering objects handed to it
- Formatting
- Human legibility
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import math


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _safe_date(ts: Optional[float]) -> str:
    if ts is None:
        return "unknown"
    return datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S UTC")


def _bar(value: float, width: int = 30) -> str:
    v = max(-1.0, min(1.0, float(value)))
    midpoint = width // 2
    pos = int((v + 1) / 2 * width)

    out = ""
    for i in range(width):
        if i == midpoint:
            out += "|"
        elif i < pos:
            out += "█"
        else:
            out += " "
    return out


def _narrative(state: str, season: str) -> str:
    if state == "Still":
        return "The system holds its breath; a quiet neutrality prevails."
    if state == "Turbulent":
        return "Crosscurrents stir beneath the surface."
    if state == "Resonant":
        return "Patterns align without force."
    return "The rhythm is faint today — listen closely."


# ---------------------------------------------------------------------
# Dashboard Renderer
# ---------------------------------------------------------------------
def render_signal_dashboard(
    *,
    t: float,
    field_sample: Any,
    field_waves: Dict[str, Any],
    domain_waves: List[Any],
    oracle_descriptors: List[Any],
    oracle_convergence: List[Any],
    oracle_phase: Optional[Any] = None,
    shepherd_posture: Optional[Any] = None,
    execution_gate: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:

    context = context or {}
    season = context.get("season", "?")
    state = context.get("state", "?")

    print("\n" + "═" * 78)
    print("                     📡 RHYTHM OS — SIGNAL DASHBOARD")
    print("═" * 78)

    print(f"  Time:            {_safe_date(t)}")
    print(f"  Season:          {season}")

    if shepherd_posture is not None:
        print(f"  Shepherd:        {shepherd_posture.posture}")
    else:
        print(f"  Shepherd:        (none)")

    if execution_gate is not None:
        print(f"  Exec Gate:       {execution_gate.state}")

    if oracle_phase is not None and oracle_phase.phase_label is not None:
        print(f"  Oracle Phase:    {oracle_phase.phase_label}")

    print(f"  State:           {state}")

    # -----------------------------------------------------------------
    # FIELD
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  FIELD (SOVEREIGN)")
    print(f"    • Coherence R:  {field_sample.coherence:.4f}")

    for name, phase in field_sample.phases.items():
        print(f"    • {name:12s}: {math.degrees(phase):8.2f}°")

    # -----------------------------------------------------------------
    # FIELD WAVES
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  FIELD WAVES (MATERIALIZED)")
    for name, w in field_waves.items():
        print(
            f"    • {name:12s} "
            f"ϕ={math.degrees(w.phase):7.2f}°  "
            f"sin={w.sine:+.3f}"
        )

    # -----------------------------------------------------------------
    # DOMAIN WAVES
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  DOMAIN WAVES (DESCRIPTIVE, NON-AUTH)")
    if domain_waves:
        for w in domain_waves:
            print(
                f"    • {w.domain}.{w.channel}: "
                f"Δϕ={w.phase_diff:+.3f} rad  "
                f"coh={w.coherence:.3f}"
            )
    else:
        print("    • (none)")

    # -----------------------------------------------------------------
    # ORACLE DESCRIPTORS
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  ORACLE — ALIGNMENT DESCRIPTORS")
    if oracle_descriptors:
        for d in oracle_descriptors:
            print(
                f"    • {d.domain}.{d.channel} vs {d.field_cycle}: "
                f"{d.pattern}"
            )
            if d.coherence_ext is not None:
                print(
                    f"      Δϕ={d.phase_diff_deg:+.1f}°  "
                    f"coh={d.coherence_ext:.3f}"
                )
            else:
                print(
                    f"      Δϕ={d.phase_diff_deg:+.1f}°  "
                    f"coh=(none)"
                )
    else:
        print("    • (none)")

    # -----------------------------------------------------------------
    # ORACLE CONVERGENCE
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  ORACLE — CONVERGENCE SUMMARY")
    if oracle_convergence:
        for c in oracle_convergence:
            print(f"    • Cycle: {c.field_cycle}")
            print(
                f"      Within ±{c.within_deg:.1f}°: "
                f"{c.within_count}/{c.active_channels}"
            )
            print(f"      Mean coherence: {c.mean_coherence:.3f}")
            print(f"      Level: {c.convergence}")
            if c.note:
                print(f"      Note: {c.note}")
    else:
        print("    • (none)")

    # -----------------------------------------------------------------
    # NARRATIVE
    # -----------------------------------------------------------------
    print("─" * 78)
    print("  NARRATIVE")
    print(f"    {_narrative(state, season)}")

    print("═" * 78 + "\n")

"""
LEGACY MODULE — ARCHIVED

This file is preserved for historical reference only.
It MUST NOT be imported or executed.
Superseded by: rhythm_os.ui.signal_scope
"""
