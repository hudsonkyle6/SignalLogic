"""
Tests for rhythm_os.voice.guards

Modules covered:
- VoiceGuardViolation
- extract_verdict_and_rationale
- truncate_to_sentences

Invariants:
- extract_verdict_and_rationale raises VoiceGuardViolation on empty text
- extract_verdict_and_rationale raises VoiceGuardViolation when first word not in valid_labels
- extract_verdict_and_rationale returns (verdict, rationale) on valid input
- extract_verdict_and_rationale is case-insensitive on the verdict word
- extract_verdict_and_rationale strips trailing punctuation from verdict
- extract_verdict_and_rationale allows empty rationale
- truncate_to_sentences returns text unchanged when <= max_sentences
- truncate_to_sentences truncates at max_sentences sentence boundary
- truncate_to_sentences handles text with no sentence boundaries
"""

from __future__ import annotations

import pytest

from rhythm_os.voice.guards import (
    VoiceGuardViolation,
    extract_verdict_and_rationale,
    truncate_to_sentences,
)

_TYPES = frozenset({"NOISE", "COUPLING", "LAG"})
_RECS = frozenset({"PROCEED", "DEFER"})


# ---------------------------------------------------------------------------
# extract_verdict_and_rationale
# ---------------------------------------------------------------------------


class TestExtractVerdictAndRationale:
    def test_valid_noise(self):
        verdict, rationale = extract_verdict_and_rationale(
            "NOISE The two domains share a daily rhythm.", _TYPES
        )
        assert verdict == "NOISE"
        assert rationale == "The two domains share a daily rhythm."

    def test_valid_coupling(self):
        verdict, rationale = extract_verdict_and_rationale(
            "COUPLING The domains converge irregularly.", _TYPES
        )
        assert verdict == "COUPLING"

    def test_valid_lag(self):
        verdict, rationale = extract_verdict_and_rationale(
            "LAG Natural consistently leads system.", _TYPES
        )
        assert verdict == "LAG"
        assert "Natural" in rationale

    def test_valid_proceed(self):
        verdict, rationale = extract_verdict_and_rationale(
            "PROCEED The convergence is confirmed.", _RECS
        )
        assert verdict == "PROCEED"

    def test_valid_defer(self):
        verdict, rationale = extract_verdict_and_rationale(
            "DEFER Insufficient evidence at this time.", _RECS
        )
        assert verdict == "DEFER"

    def test_case_insensitive_verdict(self):
        verdict, _ = extract_verdict_and_rationale("noise The signal is noise.", _TYPES)
        assert verdict == "NOISE"

    def test_mixed_case_verdict(self):
        verdict, _ = extract_verdict_and_rationale(
            "Lag The lag pattern is clear.", _TYPES
        )
        assert verdict == "LAG"

    def test_trailing_period_stripped(self):
        verdict, _ = extract_verdict_and_rationale("NOISE. Something.", _TYPES)
        assert verdict == "NOISE"

    def test_trailing_comma_stripped(self):
        verdict, _ = extract_verdict_and_rationale("LAG, rationale here.", _TYPES)
        assert verdict == "LAG"

    def test_empty_text_raises(self):
        with pytest.raises(VoiceGuardViolation, match="empty"):
            extract_verdict_and_rationale("", _TYPES)

    def test_whitespace_only_raises(self):
        with pytest.raises(VoiceGuardViolation, match="empty"):
            extract_verdict_and_rationale("   ", _TYPES)

    def test_unknown_verdict_raises(self):
        with pytest.raises(VoiceGuardViolation):
            extract_verdict_and_rationale("MAYBE something.", _TYPES)

    def test_unknown_verdict_message_contains_got(self):
        with pytest.raises(VoiceGuardViolation, match="MAYBE"):
            extract_verdict_and_rationale("MAYBE something.", _TYPES)

    def test_verdict_only_no_rationale(self):
        verdict, rationale = extract_verdict_and_rationale("NOISE", _TYPES)
        assert verdict == "NOISE"
        assert rationale == ""

    def test_rationale_with_multiple_sentences(self):
        _, rationale = extract_verdict_and_rationale(
            "LAG First sentence. Second sentence.", _TYPES
        )
        assert "First sentence" in rationale
        assert "Second sentence" in rationale

    def test_leading_whitespace_ignored(self):
        verdict, _ = extract_verdict_and_rationale("  NOISE something.", _TYPES)
        assert verdict == "NOISE"


# ---------------------------------------------------------------------------
# truncate_to_sentences
# ---------------------------------------------------------------------------


class TestTruncateToSentences:
    def test_one_sentence_unchanged(self):
        text = "The system observed twelve packets."
        assert truncate_to_sentences(text, max_sentences=2) == text

    def test_two_sentences_unchanged(self):
        text = "First sentence. Second sentence."
        assert truncate_to_sentences(text, max_sentences=2) == text

    def test_three_sentences_truncated_to_two(self):
        text = "First. Second. Third."
        result = truncate_to_sentences(text, max_sentences=2)
        assert "First" in result
        assert "Second" in result
        assert "Third" not in result

    def test_empty_text_returns_empty(self):
        assert truncate_to_sentences("", max_sentences=2) == ""

    def test_no_sentence_boundary_returns_unchanged(self):
        text = "No period here"
        assert truncate_to_sentences(text, max_sentences=2) == text

    def test_exclamation_counts_as_boundary(self):
        text = "First! Second! Third!"
        result = truncate_to_sentences(text, max_sentences=1)
        assert "Second" not in result
        assert "Third" not in result

    def test_question_mark_counts_as_boundary(self):
        text = "First? Second? Third?"
        result = truncate_to_sentences(text, max_sentences=1)
        assert "Third" not in result

    def test_max_sentences_one(self):
        text = "Only this. Not this. Nor this."
        result = truncate_to_sentences(text, max_sentences=1)
        assert result == "Only this."

    def test_preserves_content_within_limit(self):
        text = "The system admitted twelve packets. Convergence was detected."
        result = truncate_to_sentences(text, max_sentences=2)
        assert "twelve packets" in result
        assert "Convergence" in result
