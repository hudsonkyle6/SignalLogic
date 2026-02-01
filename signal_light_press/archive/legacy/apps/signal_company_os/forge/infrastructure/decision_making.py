import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from decision_schema import Decision

DECISIONS_DIR = Path("artifacts/decisions")
DECISIONS_DIR.mkdir(parents=True, exist_ok=True)


def record_decision(
    proposal_id: str,
    decision: str,
    rationale: str,
) -> Decision:
    record: Decision = {
        "proposal_id": proposal_id,
        "decision": decision,
        "rationale": rationale,
        "decided_at": datetime.utcnow().isoformat(),
    }

    path = DECISIONS_DIR / f"{proposal_id}.json"
    path.write_text(json.dumps(record, indent=2))

    return record
