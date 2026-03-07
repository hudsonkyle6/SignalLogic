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

import concurrent.futures
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

The helm state is the system's operational posture recommendation:
  WAIT    — conditions adverse or in flux; hold position
  PREPARE — conditions shifting; get ready to move
  ACT     — stable and favorable; execute planned work
  PUSH    — rare optimal window; maximum disciplined effort

Rules:
- Write exactly 3 sentences.
- Use plain past tense. No present or future tense.
- No markdown, no lists, no headers, no bullet points.
- Sentence 1: lead with the most significant observation (convergence if present).
- Sentence 2: describe the routing and system condition.
- Sentence 3: state the helm recommendation and its rationale in plain language.
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

    # Helm recommendation
    helm_state = cycle_summary.get("helm_state", "")
    helm_rationale = cycle_summary.get("helm_rationale", "")
    if helm_state:
        lines.append(f"  Helm recommendation: {helm_state} — {helm_rationale}")

    lines.append("\nWrite your 3-sentence narration:")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# narrate
# ---------------------------------------------------------------------------


_NARRATOR_TIMEOUT = 30  # seconds — hard cap on LLM call to protect main cycle
_NARRATOR_FALLBACK = "No narration available — voice timeout."


def narrate(
    cycle_summary: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    generate_fn: Optional[Callable[[str], str]] = None,
    timeout: float = _NARRATOR_TIMEOUT,
) -> NarratorResult:
    """
    Generate a 2-sentence cycle narration.

    The LLM call runs in a background thread and is capped at `timeout` seconds.
    On timeout or any LLM error a safe fallback string is returned so the caller
    (dashboard, cycle runner) is never blocked.

    Parameters
    ----------
    cycle_summary   Dict of observables from the current cycle.
    model           Ollama model tag (ignored if generate_fn is provided).
    generate_fn     Optional callable (prompt: str) -> str.
                    If provided, used instead of the real Ollama client.
                    Useful for testing without a running Ollama server.
    timeout         Maximum seconds to wait for the LLM response.

    Returns
    -------
    NarratorResult  with .text (truncated narration) and .raw (raw output).
    On timeout or error, .text is the fallback string and .raw is empty.
    """
    if generate_fn is None:
        from rhythm_os.voice.ollama_client import generate as _gen

        def generate_fn(p: str) -> str:
            return _gen(p, model=model)

    prompt = build_narrator_prompt(cycle_summary)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(generate_fn, prompt)
        try:
            raw = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return NarratorResult(text=_NARRATOR_FALLBACK, raw="")
        except Exception:
            return NarratorResult(text=_NARRATOR_FALLBACK, raw="")

    text = truncate_to_sentences(raw, max_sentences=3)
    return NarratorResult(text=text, raw=raw)
