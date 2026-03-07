"""
Tests for rhythm_os.voice.narrator, .interpreter, .gate_counselor

All tests inject generate_fn so no Ollama server is needed.

Modules covered:
- build_narrator_prompt / narrate
- build_interpreter_prompt / interpret
- build_counselor_prompt / counsel

Invariants:
- narrate returns NarratorResult with .text and .raw
- narrate passes prompt containing known cycle_summary keys to generate_fn
- narrate truncates .text to <= 3 sentences (soft guard)
- narrate preserves raw LLM output in .raw unchanged
- build_narrator_prompt includes structured observation keys (not arbitrary keys)
- interpret returns InterpretationResult with .convergence_type and .rationale
- interpret raises VoiceGuardViolation when generate_fn returns non-NOISE/COUPLING/LAG
- interpret is case-insensitive on the verdict word
- counsel returns CounselorResult with .recommendation and .justification
- counsel raises VoiceGuardViolation when generate_fn returns non-PROCEED/DEFER
- build_*_prompt functions include context keys in the output string
- ollama_client.generate raises OllamaUnavailable on ConnectionError
- ollama_client.generate raises OllamaUnavailable on Timeout
- ollama_client.generate raises OllamaError on non-200 HTTP response
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rhythm_os.voice.guards import VoiceGuardViolation
from rhythm_os.voice.gate_counselor import (
    CounselorResult,
    build_counselor_prompt,
    counsel,
)
from rhythm_os.voice.interpreter import (
    InterpretationResult,
    build_interpreter_prompt,
    interpret,
)
from rhythm_os.voice.narrator import NarratorResult, build_narrator_prompt, narrate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gen(text: str):
    """Return a generate_fn that always returns the given text."""
    return lambda _prompt: text


# ---------------------------------------------------------------------------
# narrator
# ---------------------------------------------------------------------------


class TestNarrator:
    def test_returns_narrator_result(self):
        result = narrate({"packets": 5}, generate_fn=_gen("First. Second."))
        assert isinstance(result, NarratorResult)

    def test_text_field_populated(self):
        result = narrate({}, generate_fn=_gen("The system was quiet."))
        assert result.text == "The system was quiet."

    def test_raw_field_is_unchanged_llm_output(self):
        raw = "First sentence. Second sentence. Third sentence."
        result = narrate({}, generate_fn=_gen(raw))
        assert result.raw == raw

    def test_text_truncated_to_three_sentences(self):
        # Narrator contract is exactly 3 sentences; a 4th is soft-truncated.
        raw = "First. Second. Third. Fourth."
        result = narrate({}, generate_fn=_gen(raw))
        assert "Fourth" not in result.text

    def test_text_within_three_sentences_unchanged(self):
        raw = "First. Second. Third."
        result = narrate({}, generate_fn=_gen(raw))
        assert result.text == raw

    def test_text_with_one_sentence_unchanged(self):
        result = narrate({}, generate_fn=_gen("Just one sentence."))
        assert result.text == "Just one sentence."

    def test_prompt_contains_known_routing_keys(self):
        # The structured prompt builder includes routing stats and domains.
        captured = []
        narrate(
            {"packets_admitted": 10, "domains_seen": ["natural"],
             "packets_drained": 12, "rejected": 2, "spillway_quarantined": 0},
            generate_fn=lambda p: captured.append(p) or "One. Two. Three.",
        )
        assert any("admitted" in p for p in captured)
        assert any("natural" in p for p in captured)

    def test_build_narrator_prompt_contains_routing_info(self):
        # Prompt includes structured routing section; arbitrary keys are not
        # passed through verbatim (prompt builder is structured, not a dump).
        prompt = build_narrator_prompt({
            "packets_admitted": 42, "packets_drained": 50,
            "domains_seen": ["market", "natural"],
        })
        assert "42" in prompt
        assert "market" in prompt


# ---------------------------------------------------------------------------
# interpreter
# ---------------------------------------------------------------------------


class TestInterpreter:
    def test_returns_interpretation_result(self):
        result = interpret({}, generate_fn=_gen("NOISE The rhythm is daily."))
        assert isinstance(result, InterpretationResult)

    def test_noise_verdict_parsed(self):
        result = interpret({}, generate_fn=_gen("NOISE Daily shared rhythm."))
        assert result.convergence_type == "NOISE"

    def test_coupling_verdict_parsed(self):
        result = interpret({}, generate_fn=_gen("COUPLING Irregular meeting."))
        assert result.convergence_type == "COUPLING"

    def test_lag_verdict_parsed(self):
        result = interpret({}, generate_fn=_gen("LAG Natural leads system."))
        assert result.convergence_type == "LAG"

    def test_rationale_extracted(self):
        result = interpret(
            {}, generate_fn=_gen("LAG Natural consistently leads system.")
        )
        assert result.rationale == "Natural consistently leads system."

    def test_raw_field_preserved(self):
        raw = "NOISE The rhythm is predictable."
        result = interpret({}, generate_fn=_gen(raw))
        assert result.raw == raw

    def test_case_insensitive_verdict(self):
        result = interpret({}, generate_fn=_gen("noise The rhythm is daily."))
        assert result.convergence_type == "NOISE"

    def test_invalid_verdict_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            interpret({}, generate_fn=_gen("UNKNOWN Something happened."))

    def test_empty_response_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            interpret({}, generate_fn=_gen(""))

    def test_free_text_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            interpret({}, generate_fn=_gen("I think this might be noise."))

    def test_prompt_contains_summary_keys(self):
        captured = []
        try:
            interpret(
                {"domain_pair": "natural+system", "total_count": 42},
                generate_fn=lambda p: captured.append(p) or "LAG Some rationale.",
            )
        except Exception:
            pass
        assert any("domain_pair" in p for p in captured)

    def test_build_interpreter_prompt_contains_keys(self):
        prompt = build_interpreter_prompt({"domain_pair": "a+b", "count": 7})
        assert "domain_pair" in prompt
        assert "a+b" in prompt


# ---------------------------------------------------------------------------
# gate_counselor
# ---------------------------------------------------------------------------


class TestGateCounselor:
    def test_returns_counselor_result(self):
        result = counsel({}, generate_fn=_gen("PROCEED The evidence is strong."))
        assert isinstance(result, CounselorResult)

    def test_proceed_parsed(self):
        result = counsel({}, generate_fn=_gen("PROCEED Evidence confirmed."))
        assert result.recommendation == "PROCEED"

    def test_defer_parsed(self):
        result = counsel({}, generate_fn=_gen("DEFER Not enough data."))
        assert result.recommendation == "DEFER"

    def test_justification_extracted(self):
        result = counsel(
            {}, generate_fn=_gen("PROCEED The gate is open and pattern is strong.")
        )
        assert result.justification == "The gate is open and pattern is strong."

    def test_raw_field_preserved(self):
        raw = "DEFER Risk is too high at this phase."
        result = counsel({}, generate_fn=_gen(raw))
        assert result.raw == raw

    def test_case_insensitive_verdict(self):
        result = counsel({}, generate_fn=_gen("proceed The conditions are met."))
        assert result.recommendation == "PROCEED"

    def test_invalid_verdict_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            counsel({}, generate_fn=_gen("MAYBE conditions are unclear."))

    def test_empty_response_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            counsel({}, generate_fn=_gen(""))

    def test_free_text_raises_guard_violation(self):
        with pytest.raises(VoiceGuardViolation):
            counsel({}, generate_fn=_gen("I think you should proceed here."))

    def test_prompt_contains_context_keys(self):
        captured = []
        counsel(
            {"action_type": "SIGNAL", "gate_id": "g-001"},
            generate_fn=lambda p: captured.append(p) or "DEFER Insufficient evidence.",
        )
        assert any("action_type" in p for p in captured)
        assert any("gate_id" in p for p in captured)

    def test_build_counselor_prompt_contains_keys(self):
        prompt = build_counselor_prompt({"convergence_trigger": "weak:natural"})
        assert "convergence_trigger" in prompt
        assert "weak:natural" in prompt


# ---------------------------------------------------------------------------
# ollama_client (HTTP-level tests with mocked requests)
# ---------------------------------------------------------------------------


class TestOllamaClient:
    def test_returns_response_text(self):
        from rhythm_os.voice.ollama_client import generate

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "hello world"}

        with patch(
            "rhythm_os.voice.ollama_client.requests.post", return_value=mock_resp
        ):
            result = generate("test prompt")
        assert result == "hello world"

    def test_raises_ollama_unavailable_on_connection_error(self):
        import requests as req

        from rhythm_os.voice.ollama_client import OllamaUnavailable, generate

        with patch(
            "rhythm_os.voice.ollama_client.requests.post",
            side_effect=req.ConnectionError("refused"),
        ):
            with pytest.raises(OllamaUnavailable):
                generate("test")

    def test_raises_ollama_unavailable_on_timeout(self):
        import requests as req

        from rhythm_os.voice.ollama_client import OllamaUnavailable, generate

        with patch(
            "rhythm_os.voice.ollama_client.requests.post",
            side_effect=req.Timeout("timeout"),
        ):
            with pytest.raises(OllamaUnavailable):
                generate("test")

    def test_raises_ollama_error_on_non_200(self):
        from rhythm_os.voice.ollama_client import OllamaError, generate

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"

        with patch(
            "rhythm_os.voice.ollama_client.requests.post", return_value=mock_resp
        ):
            with pytest.raises(OllamaError):
                generate("test")

    def test_sends_model_in_payload(self):
        from rhythm_os.voice.ollama_client import generate

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "ok"}

        with patch(
            "rhythm_os.voice.ollama_client.requests.post", return_value=mock_resp
        ) as mock_post:
            generate("prompt", model="qwen2.5:7b")

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "qwen2.5:7b"

    def test_sends_temperature_in_options(self):
        from rhythm_os.voice.ollama_client import generate

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "ok"}

        with patch(
            "rhythm_os.voice.ollama_client.requests.post", return_value=mock_resp
        ) as mock_post:
            generate("prompt", temperature=0.5)

        payload = mock_post.call_args[1]["json"]
        assert payload["options"]["temperature"] == 0.5
