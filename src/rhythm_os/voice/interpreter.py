"""
Interpreter — convergence classification voice mode.

The Interpreter classifies a domain pair's observed convergence pattern
and articulates the rationale in one sentence. It is the LLM-powered
complement to the ConvergenceClassifier — the classifier uses hard
thresholds; the Interpreter provides language and nuance.

Contract:
  - First word MUST be exactly one of: NOISE, COUPLING, LAG
  - Followed by exactly one sentence of rationale.
  - No additional output. VoiceGuardViolation raised if format is wrong.

NOISE    = predictable shared daily rhythm, low forward signal value.
COUPLING = irregular convergence, no fixed phase or leader, high signal.
LAG      = one domain consistently precedes the other, directional signal.

Usage:
    from rhythm_os.voice.interpreter import interpret

    result = interpret(history_summary={
        "domain_pair": "natural+system",
        "total_count": 42,
        "dominant_bucket": 3,
        "top_leader": "natural",
        "top_leader_ratio": 0.71,
        "classifier_verdict": "LAG",
    })
    print(result.convergence_type)  # "LAG"
    print(result.rationale)         # "The natural domain leads..."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Optional

from rhythm_os.voice.guards import extract_verdict_and_rationale

DEFAULT_MODEL = "qwen2.5:7b"

_VALID_TYPES: FrozenSet[str] = frozenset({"NOISE", "COUPLING", "LAG"})

_INTERPRETER_INSTRUCTION = """\
You are the system Interpreter.

Classify the convergence pattern described below. Your response must follow
this exact format:

  VERDICT One sentence of rationale.

Where VERDICT is exactly one of: NOISE, COUPLING, LAG

Definitions:
  NOISE    The two domains share a predictable daily rhythm. Low signal value.
  COUPLING The domains converge irregularly with no fixed phase or leader. High signal value.
  LAG      One domain consistently precedes the other into convergence. Directional signal.

No other output. No markdown. No explanation before the verdict.
"""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterpretationResult:
    """
    Output of the Interpreter voice mode.

    convergence_type  NOISE | COUPLING | LAG
    rationale         One sentence explaining the classification.
    raw               Raw LLM output before guard parsing.
    """

    convergence_type: str
    rationale: str
    raw: str


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_interpreter_prompt(history_summary: Dict[str, Any]) -> str:
    """
    Build the full prompt for the Interpreter from a pair history summary.

    Typical keys from ConvergenceMemoryStore.pair_summary():
      domain_pair         str  e.g. "natural+system"
      total_count         int
      dominant_bucket     int or None
      leading_counts      dict[str, int]
      bucket_counts       dict[int, int]
      classifier_verdict  str  from ConvergenceClassifier (optional hint)
    """
    lines = [_INTERPRETER_INSTRUCTION, "", "Convergence history:"]
    for key, value in history_summary.items():
        lines.append(f"  {key}: {value}")
    lines.append("\nClassify:")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# interpret
# ---------------------------------------------------------------------------


def interpret(
    history_summary: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    generate_fn: Optional[Callable[[str], str]] = None,
) -> InterpretationResult:
    """
    Classify a domain pair's convergence pattern using the Interpreter.

    Parameters
    ----------
    history_summary  Dict from ConvergenceMemoryStore.pair_summary(),
                     optionally enriched with classifier_verdict.
    model            Ollama model tag (ignored if generate_fn is provided).
    generate_fn      Optional callable (prompt: str) -> str.

    Returns
    -------
    InterpretationResult  with .convergence_type, .rationale, .raw.

    Raises
    ------
    VoiceGuardViolation  If LLM output does not start with NOISE/COUPLING/LAG.
    OllamaUnavailable    If Ollama cannot be reached and no generate_fn given.
    OllamaError          If Ollama returns a non-200 status.
    """
    if generate_fn is None:
        from rhythm_os.voice.ollama_client import generate as _gen

        def generate_fn(p: str) -> str:
            return _gen(p, model=model)

    prompt = build_interpreter_prompt(history_summary)
    raw = generate_fn(prompt)
    convergence_type, rationale = extract_verdict_and_rationale(raw, _VALID_TYPES)
    return InterpretationResult(
        convergence_type=convergence_type,
        rationale=rationale,
        raw=raw,
    )
