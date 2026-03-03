"""
GateAuthority — Resolver at the end of the turbine convergence pipeline.

The authority sits between a turbine convergence observation and any
consequential action. It answers a single question:

    "Given the current gate state and system posture, may the turbine
     execute this action?"

Decision hierarchy (checked in order):
  1. System posture — OBSERVATORY_ONLY always produces BLOCK
  2. Gate existence — if no gate is open for this scope, BLOCK
  3. Mandate freshness — gate's mandate must still be fresh
  4. Scope match — action type must match gate scope
  => PROCEED if all checks pass

The kill-switch invariant is preserved: the authority NEVER prevents a
gate from being closed. Close operations bypass authority checks entirely.

Usage:
    from rhythm_os.control_plane.gate_authority import GateAuthority
    from rhythm_os.control_plane.gate_store import GateStore, ActionScope
    from rhythm_os.control_plane.turbine_action import ActionType

    store = GateStore()
    authority = GateAuthority(store)

    result = authority.evaluate(
        action_type=ActionType.SIGNAL,
        gate_id="gate-001",
        mandate=loaded_mandate,
    )
    if result.decision == AuthorityDecision.PROCEED:
        ...
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rhythm_os.core.posture import SYSTEM_POSTURE
from rhythm_os.control_plane.mandate import Mandate, is_fresh
from rhythm_os.control_plane.gate_store import (
    ActionScope,
    Gate,
    GateState,
    GateStore,
)
from rhythm_os.control_plane.turbine_action import (
    ActionOutcome,
    ActionType,
    TurbineAction,
    append_turbine_action,
    make_turbine_action,
)


# ---------------------------------------------------------------------------
# Decision types
# ---------------------------------------------------------------------------


class AuthorityDecision(str, Enum):
    PROCEED = "PROCEED"
    DEFER = "DEFER"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class AuthorityResult:
    decision: AuthorityDecision
    reason: str
    gate_id: Optional[str] = None
    gate: Optional[Gate] = None


# ---------------------------------------------------------------------------
# Scope ↔ ActionType mapping
# ---------------------------------------------------------------------------

_SCOPE_FOR_ACTION: Dict[ActionType, ActionScope] = {
    ActionType.SIGNAL: ActionScope.SIGNAL,
    ActionType.ROUTE_ADJUST: ActionScope.ROUTE_ADJUST,
    ActionType.EXTERNAL: ActionScope.EXTERNAL,
    ActionType.GATE_CONTROL: ActionScope.GATE_CONTROL,
}


# ---------------------------------------------------------------------------
# GateAuthority
# ---------------------------------------------------------------------------


class GateAuthority:
    """
    Authority resolver.

    Injecting the GateStore at construction time makes the authority
    testable without touching real filesystem paths.
    """

    def __init__(
        self,
        gate_store: Optional[GateStore] = None,
        *,
        persist_actions: bool = True,
        store_dir: Optional[Path] = None,
    ) -> None:
        self._store = gate_store or GateStore()
        self._persist = persist_actions
        self._store_dir = store_dir  # forwarded to append_turbine_action

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        action_type: ActionType,
        gate_id: str,
        mandate: Optional[Mandate] = None,
        now: Optional[float] = None,
    ) -> AuthorityResult:
        """
        Evaluate whether the turbine may execute an action.

        Checks (in order):
          1. OBSERVATORY_ONLY posture → BLOCK always
          2. Gate must exist and be OPEN
          3. Gate scope must match action type
          4. Mandate must be present and fresh (if available)

        Does NOT perform any action. Side-effect-free.
        """
        # 1. Posture check — non-negotiable
        if SYSTEM_POSTURE == "OBSERVATORY_ONLY":
            return AuthorityResult(
                decision=AuthorityDecision.BLOCK,
                reason="posture=OBSERVATORY_ONLY",
                gate_id=gate_id,
            )

        # 2. Gate existence and state
        gate = self._store.get_gate(gate_id)
        if gate is None:
            return AuthorityResult(
                decision=AuthorityDecision.BLOCK,
                reason="gate_not_found",
                gate_id=gate_id,
            )
        if gate.state == GateState.CLOSED:
            return AuthorityResult(
                decision=AuthorityDecision.BLOCK,
                reason="gate_closed",
                gate_id=gate_id,
                gate=gate,
            )

        # 3. Scope match
        required_scope = _SCOPE_FOR_ACTION.get(action_type)
        if required_scope is None or gate.scope != required_scope:
            return AuthorityResult(
                decision=AuthorityDecision.BLOCK,
                reason=f"scope_mismatch:gate={gate.scope.value},action={action_type.value}",
                gate_id=gate_id,
                gate=gate,
            )

        # 4. Mandate freshness (best-effort when mandate is provided)
        if mandate is not None:
            t = int(time.time()) if now is None else int(now)
            if not is_fresh(mandate, now=t):
                return AuthorityResult(
                    decision=AuthorityDecision.BLOCK,
                    reason="stale_or_expired_mandate",
                    gate_id=gate_id,
                    gate=gate,
                )

        return AuthorityResult(
            decision=AuthorityDecision.PROCEED,
            reason="gate_open_scope_match",
            gate_id=gate_id,
            gate=gate,
        )

    # ------------------------------------------------------------------
    # Action execution wrapper
    # ------------------------------------------------------------------

    def resolve_action(
        self,
        *,
        action_type: ActionType,
        gate_id: str,
        convergence_trigger: str,
        proposed_payload: Dict[str, Any],
        mandate: Optional[Mandate] = None,
        executor: Optional[Callable[[TurbineAction], None]] = None,
        counsel_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        now: Optional[float] = None,
    ) -> TurbineAction:
        """
        Full action lifecycle: counsel (advisory) → evaluate → act → log → return.

        Parameters
        ----------
        action_type          The type of action being proposed
        gate_id              Gate to consult for authorization
        convergence_trigger  Convergence note that caused this proposal
        proposed_payload     Structured payload for the action
        mandate              Optional mandate to check for freshness
        executor             Optional callable that carries out the action.
                             Called only when authority says PROCEED.
                             If executor raises, outcome becomes FAILED.
        counsel_fn           Optional callable (action_context: Dict) -> CounselorResult.
                             If omitted, the real Gate Counselor (Ollama) is used.
                             Errors from the counselor are swallowed — advisory only.
        now                  Override clock for testing

        Returns a fully-populated TurbineAction with outcome recorded.
        """
        t = now if now is not None else time.time()

        # ------------------------------------------------------------------
        # Gate Counselor advisory — runs before authority evaluation.
        # The counselor NEVER blocks; its verdict is logged alongside the
        # authority's hard decision.  Errors are swallowed silently.
        # ------------------------------------------------------------------
        counselor_verdict: Optional[str] = None
        counselor_justification: Optional[str] = None
        try:
            if counsel_fn is None:
                from rhythm_os.voice.gate_counselor import counsel as _counsel

                def counsel_fn(ctx: Dict[str, Any]) -> Any:
                    return _counsel(ctx)

            action_context: Dict[str, Any] = {
                "action_type": action_type.value,
                "gate_id": gate_id,
                "convergence_trigger": convergence_trigger,
                **proposed_payload,
            }
            cr = counsel_fn(action_context)
            counselor_verdict = cr.recommendation
            counselor_justification = cr.justification
            # Persist counselor advisory as a voice line for the dashboard
            from rhythm_os.voice.voice_store import VoiceLine, persist_voice_line

            persist_voice_line(
                VoiceLine(
                    mode="counselor",
                    text=f"{cr.recommendation}: {cr.justification}",
                    raw=cr.raw,
                )
            )
        except Exception:
            pass  # advisory only — never raise

        result = self.evaluate(
            action_type=action_type,
            gate_id=gate_id,
            mandate=mandate,
            now=now,
        )

        if result.decision == AuthorityDecision.PROCEED:
            # Build a provisional action record
            action = make_turbine_action(
                action_type=action_type,
                gate_id=gate_id,
                convergence_trigger=convergence_trigger,
                proposed_payload=proposed_payload,
                outcome=ActionOutcome.EXECUTED,
                outcome_reason=result.reason,
                t=t,
                acted_at=t,
                counselor_verdict=counselor_verdict,
                counselor_justification=counselor_justification,
            )
            # Run executor if provided
            if executor is not None:
                try:
                    executor(action)
                except Exception as exc:
                    action = make_turbine_action(
                        action_type=action_type,
                        gate_id=gate_id,
                        convergence_trigger=convergence_trigger,
                        proposed_payload=proposed_payload,
                        outcome=ActionOutcome.FAILED,
                        outcome_reason=f"executor_error:{exc}",
                        t=t,
                        acted_at=time.time(),
                        counselor_verdict=counselor_verdict,
                        counselor_justification=counselor_justification,
                    )
        else:
            action = make_turbine_action(
                action_type=action_type,
                gate_id=gate_id,
                convergence_trigger=convergence_trigger,
                proposed_payload=proposed_payload,
                outcome=ActionOutcome.BLOCKED,
                outcome_reason=result.reason,
                t=t,
                acted_at=t,
                counselor_verdict=counselor_verdict,
                counselor_justification=counselor_justification,
            )

        if self._persist:
            append_turbine_action(action, store_dir=self._store_dir)

        return action
