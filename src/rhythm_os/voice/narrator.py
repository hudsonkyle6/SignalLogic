"""
Narrator — post-cycle dashboard narration voice mode.

The Narrator describes what the system observed during the last cycle in
plain language, suitable for display in the helix dashboard panel.

Contract:
  - At most 2 sentences. The guard truncates excess output.
  - Past tense only. No predictions, recommendations, or speculation.
  - Plain text. No markdown, no headers, no lists.
  - If nothing of note occurred, it says so plainly.

Usage:
    from rhythm_os.voice.narrator import narrate

    result = narrate(cycle_summary={
        "packets_admitted": 12,
        "domains_seen": ["natural", "system"],
        "convergence_notes": ["weak:natural", "convergence:natural,system"],
        "gate_actions_taken": 0,
    })
    print(result.text)   # → "Twelve packets were admitted across two domains..."

The generate_fn parameter allows tests to inject a mock without Ollama running.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from rhythm_os.voice.guards import truncate_to_sentences

DEFAULT_MODEL = "qwen2.5:7b"

_NARRATOR_INSTRUCTION = """\
You are the system Narrator.

Rules:
- Write exactly 2 sentences. No more, no fewer.
- Use plain past tense. No present or future tense.
- No predictions, recommendations, or speculation.
- No markdown, no lists, no headers, no bullet points.
- State only what the data shows. Nothing else.
"""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NarratorResult:
    """
    Output of the Narrator voice mode.

    text  The narration (at most 2 sentences, soft-truncated by guard).
    raw   The raw LLM output before truncation.
    """

    text: str
    raw: str


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_narrator_prompt(cycle_summary: Dict[str, Any]) -> str:
    """
    Build the full prompt for the Narrator from a cycle summary dict.

    The dict may contain any keys the caller finds relevant. Typical keys:
      packets_admitted    int
      domains_seen        list[str]
      convergence_notes   list[str]
      gate_actions_taken  int
      system_count        int
      natural_count       int
    """
    lines = [_NARRATOR_INSTRUCTION, "", "Cycle summary:"]
    for key, value in cycle_summary.items():
        lines.append(f"  {key}: {value}")
    lines.append("\nWrite your 2-sentence narration:")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# narrate
# ---------------------------------------------------------------------------


def narrate(
    cycle_summary: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    generate_fn: Optional[Callable[[str], str]] = None,
) -> NarratorResult:
    """
    Generate a 2-sentence cycle narration.

    Parameters
    ----------
    cycle_summary   Dict of observables from the current cycle.
    model           Ollama model tag (ignored if generate_fn is provided).
    generate_fn     Optional callable (prompt: str) -> str.
                    If provided, used instead of the real Ollama client.
                    Useful for testing without a running Ollama server.

    Returns
    -------
    NarratorResult  with .text (truncated narration) and .raw (raw output).

    Raises
    ------
    OllamaUnavailable  If Ollama cannot be reached and no generate_fn given.
    OllamaError        If Ollama returns a non-200 status.
    """
    if generate_fn is None:
        from rhythm_os.voice.ollama_client import generate as _gen

        def generate_fn(p: str) -> str:
            return _gen(p, model=model)

    prompt = build_narrator_prompt(cycle_summary)
    raw = generate_fn(prompt)
    text = truncate_to_sentences(raw, max_sentences=2)
    return NarratorResult(text=text, raw=raw)
