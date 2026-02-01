"""
Field Cycle Validation (Descriptive)

AUTHORITY: Signal Light Press
CLASSIFICATION: RUNTIME SUPPORT
EXECUTABLE: NO
DECISION AUTHORITY: NONE

Provides validation helpers for field_cycle values.
"""

from __future__ import annotations
from typing import Iterable

CANONICAL_FIELD_CYCLES = {"init", "bootstrap", "computed"}


def is_valid_field_cycle(value: str) -> bool:
    return value in CANONICAL_FIELD_CYCLES


def find_invalid_field_cycles(values: Iterable[str]) -> set[str]:
    return {v for v in values if v not in CANONICAL_FIELD_CYCLES}
