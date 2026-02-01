"""
Canonical runtime import surface for Rhythm OS foundations.

RULES:
- Runtime code imports from here
- No authority semantics live here
- Foundations expose only minimal invariants
"""

from rhythm_os.foundations_runtime.execution_gate import ExecutionGateDecision

__all__ = [
    "ExecutionGateDecision",
]
