"""
SHEPHERD OS — READ SAGE CONTEXT
Authority: Signal Light Press
Mode: Non-Executive / Assist Under Discipline
Purpose: Read Sage posture as situational context only
"""

import json
from pathlib import Path
from datetime import datetime

SAGE_STATE = Path(__file__).resolve().parents[2] / "state" / "sage_state.json"
SAGE_POSTURE_REPORTS = Path(__file__).resolve().parents[2] / "archive" / "reports" / "signal_company_posture"

def read_latest_sage_posture():
    """
    Reads Sage posture without interpreting or acting.
    Fails closed to UNKNOWN.
    """

    context = {
        "sage_present": False,
        "sage_posture": "UNKNOWN",
        "timestamp": None
    }

    if not SAGE_STATE.exists():
        return context

    try:
        with open(SAGE_STATE, "r") as f:
            state = json.load(f)

        if state.get("status") != "OK":
            return context

        reports = sorted(SAGE_POSTURE_REPORTS.glob("posture_report_*.md"))

        if not reports:
            return context

        latest = reports[-1]
        text = latest.read_text().lower()

        posture = "STABILITY"

        if "marginal" in text:
            posture = "MARGINAL_OBSERVATION"
        elif "accumulation" in text:
            posture = "ACCUMULATION"

        context.update({
            "sage_present": True,
            "sage_posture": posture,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        return context

    except Exception:
        return context
