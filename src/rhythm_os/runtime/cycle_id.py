"""
Cycle ID Generator (Descriptive)

AUTHORITY: Signal Light Press
CLASSIFICATION: RUNTIME SUPPORT
EXECUTABLE: NO
DECISION AUTHORITY: NONE
"""

from __future__ import annotations
import hashlib

__all__ = ["compute_cycle_id"]


def compute_cycle_id(*, t_ref: float, runner: str, version: str) -> str:
    payload = f"{int(t_ref)}|{runner}|{version}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
