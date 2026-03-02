"""
Trafficking Signal Compliance Layer

POSTURE: WITNESS (non-authoritative record)

Responsibilities:
- Monitor turbine convergence summaries for observations that include
  the human_trafficking domain
- Log compliance-review records for any such convergence events
- Provide a stub NCMEC CyberTipline reporting interface
- Track mandatory reporting obligations

IMPORTANT:
    This module does NOT make determinations about trafficking activity.
    It observes phase convergence patterns and flags them for human review.
    ALL reporting decisions require human authorization.

    No automatic reports are filed. The report_to_ncmec() function is a
    stub that must be reviewed and authorized by a responsible person
    before any submission is made.

Legal mandate:
    18 U.S.C. § 2258A — Electronic service providers must report apparent
    violations of child sexual exploitation laws to NCMEC.
    NCMEC CyberTipline: https://www.missingkids.org/gethelpnow/cybertipline

STATUS: STUB
    Awaiting data feed partnership before operational use.
    Reporting interface requires legal review prior to activation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rhythm_os.runtime.paths import TURBINE_DIR, MANDATES_DIR


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

COMPLIANCE_DIR = MANDATES_DIR / "trafficking"
COMPLIANCE_LOG = COMPLIANCE_DIR / "compliance_observations.jsonl"
REVIEW_QUEUE = COMPLIANCE_DIR / "review_queue.jsonl"


# ---------------------------------------------------------------------
# Turbine summary reader
# ---------------------------------------------------------------------


def _load_turbine_summaries() -> List[Dict[str, Any]]:
    """
    Read all turbine convergence summaries from today's cycle.
    Returns list of summary dicts.
    """
    path = TURBINE_DIR / "summary.jsonl"
    if not path.exists():
        return []

    summaries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            summaries.append(json.loads(line))
        except Exception:
            continue
    return summaries


# ---------------------------------------------------------------------
# Convergence filter
# ---------------------------------------------------------------------


def _extract_trafficking_events(
    summaries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter turbine summaries for convergence events that include the
    human_trafficking domain.

    Returns list of compliance observation records, each containing:
        ts:              ISO timestamp of observation
        convergence_ts:  ISO timestamp from the turbine summary
        diurnal_phase:   Phase at which convergence was observed
        domains:         All domains present in the convergence event
        strength:        "strong" or "weak"
        review_required: True (always — no automatic determination)
    """
    observations: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for summary in summaries:
        for event in summary.get("convergence_events", []):
            domains = event.get("domains", [])
            if "human_trafficking" not in domains:
                continue

            observations.append(
                {
                    "ts": now,
                    "convergence_ts": summary.get("ts", ""),
                    "diurnal_phase": event.get("diurnal_phase"),
                    "domains": domains,
                    "domain_count": event.get("domain_count"),
                    "strength": event.get("strength"),
                    "review_required": True,
                    "authorized_report_filed": False,
                }
            )

    return observations


# ---------------------------------------------------------------------
# Compliance log writer
# ---------------------------------------------------------------------


def _append_observations(observations: List[Dict[str, Any]]) -> None:
    """
    Append compliance observations to the append-only compliance log.
    Also writes to the review queue for human triage.

    Raises:
        FileNotFoundError: if COMPLIANCE_DIR does not exist.
            Caller must bootstrap this directory (operator responsibility).
    """
    if not observations:
        return

    if not COMPLIANCE_DIR.exists():
        raise FileNotFoundError(
            f"Compliance directory missing: {COMPLIANCE_DIR}\n"
            "Bootstrap with: mkdir -p {COMPLIANCE_DIR} (operator task)\n"
            "This directory must be operator-provisioned, not auto-created."
        )

    for obs in observations:
        line = json.dumps(obs, sort_keys=True, separators=(",", ":")) + "\n"
        with COMPLIANCE_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
        with REVIEW_QUEUE.open("a", encoding="utf-8") as f:
            f.write(line)


# ---------------------------------------------------------------------
# NCMEC CyberTipline reporting stub
# ---------------------------------------------------------------------


def report_to_ncmec(
    observation: Dict[str, Any],
    *,
    authorized_by: str,
    authorized_ts: Optional[str] = None,
) -> None:
    """
    STUB — Submit a compliance observation to the NCMEC CyberTipline.

    THIS FUNCTION IS NOT IMPLEMENTED.
    It must be reviewed by legal counsel and authorized by a responsible
    officer before any implementation is added.

    Parameters:
        observation:   Compliance observation record from review queue.
        authorized_by: Name/ID of the person authorizing this report.
        authorized_ts: ISO timestamp of authorization (defaults to now).

    NCMEC CyberTipline API documentation:
        https://www.missingkids.org/gethelpnow/cybertipline
        (API access requires NCMEC partnership agreement)

    Legal mandate:
        18 U.S.C. § 2258A

    Raises:
        NotImplementedError: Always. Implementation requires legal review.
    """
    raise NotImplementedError(
        "NCMEC CyberTipline reporting is not implemented.\n"
        "Steps required before this function can be activated:\n"
        "  1. Legal review of 18 U.S.C. § 2258A obligations\n"
        "  2. NCMEC partnership agreement and API access\n"
        "  3. Internal authorization policy (who can file, under what conditions)\n"
        "  4. Audit logging of all filed reports\n"
        f"  Reporting authorized by: {authorized_by}\n"
        f"  Observation: {json.dumps(observation)}"
    )


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------


def run_compliance_check() -> Dict[str, Any]:
    """
    Scan today's turbine summaries for trafficking domain convergence events
    and log them to the compliance observation queue.

    Returns:
        Dict with keys:
            summaries_scanned: int
            observations_logged: int
            review_required: bool
    """
    summaries = _load_turbine_summaries()
    observations = _extract_trafficking_events(summaries)

    if observations:
        _append_observations(observations)

    result = {
        "summaries_scanned": len(summaries),
        "observations_logged": len(observations),
        "review_required": len(observations) > 0,
    }

    if observations:
        print(
            f"COMPLIANCE: {len(observations)} trafficking convergence observation(s) "
            f"logged → review required at {REVIEW_QUEUE}"
        )
    else:
        print(
            f"COMPLIANCE: no trafficking convergence events in "
            f"{len(summaries)} turbine summaries"
        )

    return result


if __name__ == "__main__":
    run_compliance_check()
