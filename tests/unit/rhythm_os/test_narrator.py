"""
Tests for rhythm_os.voice.narrator

Modules covered:
- build_narrator_prompt
- narrate (including non-blocking thread-pool path and timeout fallback)
- NarratorResult

Invariants:
- build_narrator_prompt includes convergence section when events present
- build_narrator_prompt marks "none detected" when no events
- build_narrator_prompt includes routing stats
- build_narrator_prompt includes helm recommendation when set
- narrate calls generate_fn with the built prompt
- narrate returns NarratorResult with truncated text and raw
- narrate returns fallback on timeout
- narrate returns fallback on exception from generate_fn
- narrate respects custom timeout argument
"""

from __future__ import annotations

import time

import pytest

from rhythm_os.voice.narrator import (
    NarratorResult,
    _NARRATOR_FALLBACK,
    build_narrator_prompt,
    narrate,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _summary(**overrides):
    base = {
        "packets_admitted": 10,
        "packets_drained": 12,
        "rejected": 2,
        "spillway_quarantined": 0,
        "admission_pct": "83%",
        "convergence_events": 0,
        "strong_events": 0,
        "convergence_detail": [],
        "domains_seen": ["system", "market"],
        "helm_state": "ACT",
        "helm_rationale": "stable conditions",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# build_narrator_prompt
# ---------------------------------------------------------------------------


class TestBuildNarratorPrompt:
    def test_includes_observation_header(self):
        prompt = build_narrator_prompt(_summary())
        assert "Observation report" in prompt

    def test_no_convergence_says_none(self):
        prompt = build_narrator_prompt(_summary(convergence_events=0, strong_events=0))
        assert "none detected" in prompt.lower()

    def test_convergence_count_shown(self):
        prompt = build_narrator_prompt(
            _summary(
                convergence_events=3,
                strong_events=1,
                convergence_detail=["natural+system", "market+system"],
            )
        )
        assert "3 event" in prompt
        assert "1 strong" in prompt
        assert "natural+system" in prompt

    def test_routing_stats_shown(self):
        prompt = build_narrator_prompt(_summary(packets_admitted=7, rejected=1))
        assert "admitted=7" in prompt
        assert "rejected=1" in prompt

    def test_domains_shown(self):
        prompt = build_narrator_prompt(_summary(domains_seen=["cyber", "natural"]))
        assert "cyber" in prompt
        assert "natural" in prompt

    def test_helm_state_shown(self):
        prompt = build_narrator_prompt(_summary(helm_state="PUSH", helm_rationale="peak window"))
        assert "PUSH" in prompt
        assert "peak window" in prompt

    def test_helm_state_absent_when_empty(self):
        prompt = build_narrator_prompt(_summary(helm_state=""))
        assert "Helm recommendation:" not in prompt

    def test_no_domains_says_none(self):
        prompt = build_narrator_prompt(_summary(domains_seen=[]))
        assert "none" in prompt


# ---------------------------------------------------------------------------
# narrate — happy path
# ---------------------------------------------------------------------------


class TestNarrateHappyPath:
    def test_calls_generate_fn(self):
        called_with = []

        def fake_gen(prompt: str) -> str:
            called_with.append(prompt)
            return "The system ran smoothly. No anomalies occurred. Helm advised ACT."

        result = narrate(_summary(), generate_fn=fake_gen)
        assert len(called_with) == 1
        assert isinstance(result, NarratorResult)

    def test_result_text_is_truncated_to_3_sentences(self):
        def fake_gen(prompt: str) -> str:
            return "S1. S2. S3. S4. S5."

        result = narrate(_summary(), generate_fn=fake_gen)
        # truncate_to_sentences with max_sentences=3 should stop after S3
        assert "S4" not in result.text
        assert "S5" not in result.text

    def test_raw_is_untruncated(self):
        long = "S1. S2. S3. S4. S5."

        def fake_gen(prompt: str) -> str:
            return long

        result = narrate(_summary(), generate_fn=fake_gen)
        assert result.raw == long

    def test_result_frozen(self):
        def fake_gen(p: str) -> str:
            return "One sentence."

        result = narrate(_summary(), generate_fn=fake_gen)
        with pytest.raises(Exception):
            result.text = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# narrate — timeout / error fallback
# ---------------------------------------------------------------------------


class TestNarrateTimeout:
    def test_timeout_returns_fallback(self):
        def slow_gen(prompt: str) -> str:
            time.sleep(10)
            return "This should never be returned."

        result = narrate(_summary(), generate_fn=slow_gen, timeout=0.05)
        assert result.text == _NARRATOR_FALLBACK
        assert result.raw == ""

    def test_exception_returns_fallback(self):
        def failing_gen(prompt: str) -> str:
            raise RuntimeError("Ollama exploded")

        result = narrate(_summary(), generate_fn=failing_gen)
        assert result.text == _NARRATOR_FALLBACK
        assert result.raw == ""

    def test_connection_error_returns_fallback(self):
        def conn_gen(prompt: str) -> str:
            raise ConnectionError("refused")

        result = narrate(_summary(), generate_fn=conn_gen)
        assert result.text == _NARRATOR_FALLBACK

    def test_custom_timeout_respected(self):
        def instant_gen(prompt: str) -> str:
            return "Done quickly."

        result = narrate(_summary(), generate_fn=instant_gen, timeout=5)
        assert result.text != _NARRATOR_FALLBACK
