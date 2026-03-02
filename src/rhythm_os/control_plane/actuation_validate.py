# C:\Users\SignalADmin\Signal Archive\SignalLogic\rhythm_os\control_plane/actuation_validate.py
from __future__ import annotations

from typing import Dict, Any


class ActuationContractError(Exception):
    """
    Raised when an actuation payload violates the contract.

    This module defines validation ONLY.
    It does not execute, dispatch, or authorize anything.
    """

    pass


def validate_actuation_payload(d: Dict[str, Any]) -> None:
    """
    Validates the structural contract of an actuation payload.

    Required keys:
      - t
      - action
      - scope
      - mandate_id
      - intent_hash

    This function does NOT:
      - check permissions
      - check mandate freshness
      - perform any actuation

    It only asserts that no actuation payload can exist
    without an explicit mandate reference.
    """
    required = ["t", "action", "scope", "mandate_id", "intent_hash"]
    missing = [k for k in required if k not in d]
    if missing:
        raise ActuationContractError(f"missing keys: {missing}")

    if not str(d["mandate_id"]).strip():
        raise ActuationContractError("mandate_id empty")
