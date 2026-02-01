"""
Oracle domain package.

Descriptive only.
No authority. No posture. No narrative.
"""

from .oracle import Oracle, AlignmentDescriptor
# TEMP DISABLED: invalid import
# from .convergence_logic import OracleConvergence, ConvergenceSummary

__all__ = [
    "Oracle",
    "OracleConvergence",
    "AlignmentDescriptor",
    "ConvergenceSummary",
]
