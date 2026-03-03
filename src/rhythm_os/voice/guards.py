"""
Voice output guards — structured output validation for LLM responses.

Built from the archive guard pattern at:
  signal_light_press/archive/legacy/.../guards_and_schemas/guard.py

All voice modes require structured output: a verdict word followed by
a sentence. These guards extract and validate that structure, raising
VoiceGuardViolation if the LLM output does not comply.

Design:
  - Guards are pure functions — no I/O, no side effects.
  - Guards extract the structured part or raise; they do not retry.
  - The caller decides whether to retry, fall back, or propagate.
  - Guards are lenient about whitespace and punctuation around verdict words.
  - Guards are strict about the verdict word itself (must be exact match).
"""

from __future__ import annotations

import re
from typing import FrozenSet, Tuple


# ---------------------------------------------------------------------------
# VoiceGuardViolation
# ---------------------------------------------------------------------------


class VoiceGuardViolation(Exception):
    """
    Raised when an LLM response does not conform to the expected structure.

    The message describes what was expected vs. what was received.
    """


# ---------------------------------------------------------------------------
# extract_verdict_and_rationale
# ---------------------------------------------------------------------------


def extract_verdict_and_rationale(
    text: str,
    valid_labels: FrozenSet[str],
) -> Tuple[str, str]:
    """
    Extract (verdict, rationale) from a structured LLM response.

    The LLM is expected to output:
        VERDICT One sentence of rationale here.

    Rules:
      - The first whitespace-separated token is the verdict.
      - Trailing punctuation (.,!?:;) is stripped from the verdict.
      - The verdict is compared case-insensitively but returned uppercased.
      - Everything after the first token is the rationale (stripped).
      - Rationale may be empty if the LLM only output the verdict.

    Raises
    ------
    VoiceGuardViolation
        If the text is empty, or the first token is not in valid_labels.
    """
    text = text.strip()
    if not text:
        raise VoiceGuardViolation("empty response from model")

    parts = text.split(None, 1)
    raw_word = parts[0]

    # Strip common trailing punctuation from the verdict token
    verdict = raw_word.upper().strip(".,!?:;\"'")

    if verdict not in valid_labels:
        sorted_labels = sorted(valid_labels)
        raise VoiceGuardViolation(
            f"expected first word in {sorted_labels}, got {raw_word!r}"
        )

    rationale = parts[1].strip() if len(parts) > 1 else ""
    return verdict, rationale


# ---------------------------------------------------------------------------
# truncate_to_sentences
# ---------------------------------------------------------------------------


def truncate_to_sentences(text: str, max_sentences: int = 2) -> str:
    """
    Truncate text to at most max_sentences complete sentences.

    Sentence boundaries are detected by [.!?] followed by whitespace or
    end of string. If the text has fewer sentences than max_sentences,
    it is returned unchanged.

    This is a soft guard for the Narrator — it does not raise but
    silently truncates excess output.
    """
    text = text.strip()
    if not text:
        return text

    # Find sentence-ending positions: punctuation followed by space or EOL
    boundaries = [m.end() for m in re.finditer(r"[.!?]+[\s]+", text)]

    # Also treat end of string as a sentence boundary if text ends with .!?
    if text and text[-1] in ".!?":
        boundaries.append(len(text))

    if not boundaries:
        return text  # no sentence boundaries found — return as-is

    if len(boundaries) <= max_sentences:
        return text

    # Truncate at the max_sentences-th sentence boundary
    cut = boundaries[max_sentences - 1]
    return text[:cut].strip()
