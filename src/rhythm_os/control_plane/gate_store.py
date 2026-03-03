"""
GateStore — Persistent registry of turbine action gates.

A gate represents an explicit human authorization for the turbine to act
at a specific scope level. Gates are:
  - Opened by a human principal, referencing a mandate
  - Closed instantaneously by any caller (kill-switch — cannot be blocked)
  - Persisted as an append-only JSONL audit log

Gate Scopes (trust levels, lowest to highest authority):
  SIGNAL        Level 1 — turbine may emit forward signals to penstock
  ROUTE_ADJUST  Level 2 — turbine may suggest routing changes
  EXTERNAL      Level 3 — turbine may write to external interfaces
  GATE_CONTROL  Level 4 — turbine may open/close other gates

Invariants:
  - Closing a gate is ALWAYS instantaneous. No conditions. Cannot be blocked.
  - A gate can only be opened with a non-empty principal and mandate reference.
  - The store is append-only: every state transition is logged, never deleted.
  - get_gate() returns current state by replaying the log (last writer wins).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from rhythm_os.runtime.paths import GATES_DIR


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActionScope(str, Enum):
    """
    What the gate authorizes the turbine to do.

    Levels are ordered by authority weight. A higher scope does NOT imply
    lower scopes are also open — each gate is independent.
    """

    SIGNAL = "SIGNAL"  # Level 1: emit forward signal to penstock
    ROUTE_ADJUST = "ROUTE_ADJUST"  # Level 2: propose a routing adjustment
    EXTERNAL = "EXTERNAL"  # Level 3: write to external interface
    GATE_CONTROL = "GATE_CONTROL"  # Level 4: open or close other gates


class GateState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Gate dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    """
    Immutable snapshot of a gate at a point in time.

    gate_id     Unique identifier (human-readable or UUID)
    scope       What class of action this gate permits
    state       Current OPEN / CLOSED
    opened_at   Unix seconds when gate was opened
    opened_by   Human principal who opened it
    mandate_id  Reference to the mandate that authorized opening
    closed_at   Unix seconds when gate was closed (None if still open)
    closed_reason  Why the gate was closed (None if still open)
    """

    gate_id: str
    scope: ActionScope
    state: GateState
    opened_at: float
    opened_by: str
    mandate_id: str
    closed_at: Optional[float]
    closed_reason: Optional[str]

    def to_dict(self) -> Dict:
        return {
            "gate_id": self.gate_id,
            "scope": self.scope.value,
            "state": self.state.value,
            "opened_at": self.opened_at,
            "opened_by": self.opened_by,
            "mandate_id": self.mandate_id,
            "closed_at": self.closed_at,
            "closed_reason": self.closed_reason,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Gate":
        return Gate(
            gate_id=str(d["gate_id"]),
            scope=ActionScope(d["scope"]),
            state=GateState(d["state"]),
            opened_at=float(d["opened_at"]),
            opened_by=str(d["opened_by"]),
            mandate_id=str(d["mandate_id"]),
            closed_at=float(d["closed_at"]) if d.get("closed_at") is not None else None,
            closed_reason=str(d["closed_reason"])
            if d.get("closed_reason") is not None
            else None,
        )


# ---------------------------------------------------------------------------
# GateStore
# ---------------------------------------------------------------------------


class GateStoreError(Exception):
    """Raised on structural violations in gate operations."""


class GateStore:
    """
    Append-only JSONL gate registry.

    Every open and close event is appended to a single JSONL file.
    Current gate state is recovered by replaying the log (last event wins
    for each gate_id).

    Thread safety: Not guaranteed. Single-process use only.
    """

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self._path = store_path or (GATES_DIR / "gate_registry.jsonl")

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _append(self, record: Dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

    def _load_all(self) -> List[Dict]:
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
        return records

    def _current_gates(self) -> Dict[str, Gate]:
        """Replay log → map of gate_id → most recent Gate snapshot."""
        gates: Dict[str, Gate] = {}
        for record in self._load_all():
            try:
                g = Gate.from_dict(record)
                gates[g.gate_id] = g
            except Exception:
                continue
        return gates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_gate(
        self,
        gate_id: str,
        scope: ActionScope,
        opened_by: str,
        mandate_id: str,
        now: Optional[float] = None,
    ) -> Gate:
        """
        Open a gate. Persists to the audit log immediately.

        Raises GateStoreError if gate_id or opened_by is empty,
        or if the gate is already OPEN.
        """
        if not gate_id.strip():
            raise GateStoreError("gate_id must not be empty")
        if not opened_by.strip():
            raise GateStoreError("opened_by must not be empty")
        if not mandate_id.strip():
            raise GateStoreError("mandate_id must not be empty")

        existing = self._current_gates().get(gate_id)
        if existing is not None and existing.state == GateState.OPEN:
            raise GateStoreError(f"gate '{gate_id}' is already OPEN")

        t = now if now is not None else time.time()
        gate = Gate(
            gate_id=gate_id,
            scope=scope,
            state=GateState.OPEN,
            opened_at=t,
            opened_by=opened_by,
            mandate_id=mandate_id,
            closed_at=None,
            closed_reason=None,
        )
        self._append(gate.to_dict())
        return gate

    def close_gate(
        self,
        gate_id: str,
        reason: str = "operator_close",
        now: Optional[float] = None,
    ) -> Gate:
        """
        Close a gate.

        KILL-SWITCH INVARIANT:
          Closing is ALWAYS instantaneous. No conditions. No checks.
          Cannot be blocked. Closing an already-closed gate is a no-op
          (returns the existing closed state without error).

        The audit log always records the close event regardless.
        """
        existing = self._current_gates().get(gate_id)

        t = now if now is not None else time.time()

        if existing is None:
            # Gate never existed — create a synthetic closed record so the
            # intent (close) is always honoured and logged.
            opened_at = t
            scope = ActionScope.SIGNAL
            opened_by = "unknown"
            mandate_id = "unknown"
        else:
            opened_at = existing.opened_at
            scope = existing.scope
            opened_by = existing.opened_by
            mandate_id = existing.mandate_id

        gate = Gate(
            gate_id=gate_id,
            scope=scope,
            state=GateState.CLOSED,
            opened_at=opened_at,
            opened_by=opened_by,
            mandate_id=mandate_id,
            closed_at=t,
            closed_reason=reason,
        )
        self._append(gate.to_dict())
        return gate

    def get_gate(self, gate_id: str) -> Optional[Gate]:
        """Return current Gate state, or None if gate has never been opened."""
        return self._current_gates().get(gate_id)

    def is_open(self, gate_id: str) -> bool:
        """True if gate exists and is currently OPEN."""
        g = self.get_gate(gate_id)
        return g is not None and g.state == GateState.OPEN

    def list_open_gates(self) -> List[Gate]:
        """Return all currently open gates, sorted by opened_at."""
        gates = [g for g in self._current_gates().values() if g.state == GateState.OPEN]
        return sorted(gates, key=lambda g: g.opened_at)

    def list_all_gates(self) -> List[Gate]:
        """Return most-recent state for every known gate."""
        gates = list(self._current_gates().values())
        return sorted(gates, key=lambda g: g.opened_at)
