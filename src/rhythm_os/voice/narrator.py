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
You are the Narrator for a rhythmic signal observatory.

SignalLogic observes oscillatory phase alignment across physical domains —
market, natural environment, system, and cyber. When two or more domains
reach the same oscillatory phase simultaneously, a convergence event is
recorded. Strong convergence involves three or more domains aligning.

Rules:
- Write exactly 3 sentences.
- Use plain past tense. No present or future tense.
- No predictions, recommendations, or speculation.
- No markdown, no lists, no headers, no bullet points.
- Lead with the most significant observation. If convergence events occurred,
  name the domains involved and the time of day they aligned.
- If no convergence occurred, describe the system's dominant condition plainly.
- Write for a non-technical reader. State only what the data shows.
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

    Organises the summary by significance so the LLM leads with
    convergence events when present, then routing health, then domains.
    """
    lines = [_NARRATOR_INSTRUCTION, "", "Observation report:"]

    # Convergence section — most significant
    strong = cycle_summary.get("strong_events", 0)
    event_count = cycle_summary.get("convergence_events", 0)
    detail = cycle_summary.get("convergence_detail", [])
    if strong or event_count:
        lines.append(
            f"  Convergence: {event_count} event(s), {strong} strong (3+ domains)"
        )
        for d in detail:
            lines.append(f"    · {d}")
    else:
        lines.append("  Convergence: none detected this cycle")

    # Routing health
    admitted = cycle_summary.get("packets_admitted", 0)
    drained = cycle_summary.get("packets_drained", 0)
    rejected = cycle_summary.get("rejected", 0)
    anomalies = cycle_summary.get("spillway_quarantined", 0)
    pct = cycle_summary.get("admission_pct", "")
    lines.append(
        f"  Routing: drained={drained}  admitted={admitted} ({pct})"
        f"  rejected={rejected}  anomalies={anomalies}"
    )

    # Domains
    domains = cycle_summary.get("domains_seen", [])
    lines.append(
        f"  Domains observed: {', '.join(domains) if domains else 'none'}"
    )

    lines.append("\nWrite your 3-sentence narration:")
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
    text = truncate_to_sentences(raw, max_sentences=3)
    return NarratorResult(text=text, raw=raw)
