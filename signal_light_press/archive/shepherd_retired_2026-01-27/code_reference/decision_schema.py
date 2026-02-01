#decision_schema.py
from typing import Literal, TypedDict
from datetime import datetime


class Decision(TypedDict):
    proposal_id: str
    decision: Literal["approved", "rejected"]
    rationale: str
    decided_at: str  # ISO 8601
