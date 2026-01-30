from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time


@dataclass(frozen=True)
class IntervalMandate:
    mandate_id: str
    created_ts: float
    start_ts: float
    end_ts: float

    domain_scope_whitelist: List[str]
    task_whitelist: List[str]
    forbidden: List[str] = field(default_factory=list)

    justification: str = ""
    constraints: Dict[str, str] = field(default_factory=dict)
    operator_note: str = ""  # human modifications or clarifications


def is_expired(m: IntervalMandate, now_ts: Optional[float] = None) -> bool:
    now = time.time() if now_ts is None else now_ts
    return now >= m.end_ts
