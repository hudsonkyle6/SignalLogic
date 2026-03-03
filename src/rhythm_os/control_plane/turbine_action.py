"""
TurbineAction — Typed model for actions proposed and resolved by the turbine.

A TurbineAction is the formal record of:
  1. What the turbine proposed to do (action_type, proposed_payload)
  2. Which gate it referenced (gate_id)
  3. What triggered the proposal (convergence_trigger)
  4. How the authority resolved it (outcome, outcome_reason)
  5. When all of this happened (t, acted_at)

Every TurbineAction is persisted to an append-only daily JSONL log.
No TurbineAction is ever mutated after creation.

Action Types mirror GateScope levels:
  SIGNAL        Emit a forward signal to penstock
  ROUTE_ADJUST  Propose a routing change
  EXTERNAL      Write to an external interface
  GATE_CONTROL  Open or close another gate

Outcomes:
  EXECUTED  Authority approved and action was carried out
  DEFERRED  Authority approved but action awaits a future condition
  BLOCKED   Authority denied (posture, gate closed, no mandate, etc.)
  FAILED    Authority approved but execution raised an error
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from rhythm_os.runtime.paths import GATE_ACTIONS_DIR


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActionType(str, Enum):
    SIGNAL = "SIGNAL"
    ROUTE_ADJUST = "ROUTE_ADJUST"
    EXTERNAL = "EXTERNAL"
    GATE_CONTROL = "GATE_CONTROL"


class ActionOutcome(str, Enum):
    EXECUTED = "EXECUTED"
    DEFERRED = "DEFERRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# TurbineAction dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurbineAction:
    """
    Immutable record of a single turbine action proposal + resolution.

    action_id           Unique ID for this action record (UUID)
    t                   Unix seconds when the action was proposed
    action_type         What the turbine wanted to do
    gate_id             Which gate was consulted
    convergence_trigger The convergence note that triggered the proposal
    proposed_payload    Structured content of the proposed action
    outcome             How the authority resolved it
    outcome_reason      Human-readable explanation of the outcome
    acted_at            Unix seconds when resolution was recorded
    """

    action_id: str
    t: float
    action_type: ActionType
    gate_id: str
    convergence_trigger: str
    proposed_payload: Dict[str, Any]
    outcome: ActionOutcome
    outcome_reason: str
    acted_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "t": self.t,
            "action_type": self.action_type.value,
            "gate_id": self.gate_id,
            "convergence_trigger": self.convergence_trigger,
            "proposed_payload": self.proposed_payload,
            "outcome": self.outcome.value,
            "outcome_reason": self.outcome_reason,
            "acted_at": self.acted_at,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TurbineAction":
        return TurbineAction(
            action_id=str(d["action_id"]),
            t=float(d["t"]),
            action_type=ActionType(d["action_type"]),
            gate_id=str(d["gate_id"]),
            convergence_trigger=str(d["convergence_trigger"]),
            proposed_payload=dict(d.get("proposed_payload") or {}),
            outcome=ActionOutcome(d["outcome"]),
            outcome_reason=str(d["outcome_reason"]),
            acted_at=float(d["acted_at"]),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_turbine_action(
    *,
    action_type: ActionType,
    gate_id: str,
    convergence_trigger: str,
    proposed_payload: Dict[str, Any],
    outcome: ActionOutcome,
    outcome_reason: str,
    t: Optional[float] = None,
    acted_at: Optional[float] = None,
) -> TurbineAction:
    """
    Construct a TurbineAction with a fresh UUID and timestamps.
    """
    now = time.time()
    return TurbineAction(
        action_id=str(uuid.uuid4()),
        t=t if t is not None else now,
        action_type=action_type,
        gate_id=gate_id,
        convergence_trigger=convergence_trigger,
        proposed_payload=proposed_payload,
        outcome=outcome,
        outcome_reason=outcome_reason,
        acted_at=acted_at if acted_at is not None else now,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def append_turbine_action(
    action: TurbineAction, store_dir: Optional[Path] = None
) -> None:
    """
    Append a TurbineAction to the daily JSONL action log.
    Append-only. No overwrites.
    """
    directory = store_dir or GATE_ACTIONS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date().isoformat()
    path = directory / f"actions-{today}.jsonl"

    line = json.dumps(action.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def load_turbine_actions(
    store_dir: Optional[Path] = None,
    *,
    gate_id: Optional[str] = None,
    action_type: Optional[ActionType] = None,
    max_records: int = 500,
) -> list[TurbineAction]:
    """
    Load recent TurbineAction records from the action log.

    Optionally filter by gate_id or action_type.
    Returns up to max_records, most-recent first.
    """
    directory = store_dir or GATE_ACTIONS_DIR
    if not directory.exists():
        return []

    records: list[TurbineAction] = []
    for path in sorted(directory.glob("actions-*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                a = TurbineAction.from_dict(json.loads(line))
            except Exception:
                continue
            if gate_id is not None and a.gate_id != gate_id:
                continue
            if action_type is not None and a.action_type != action_type:
                continue
            records.append(a)
            if len(records) >= max_records:
                return records

    return records
