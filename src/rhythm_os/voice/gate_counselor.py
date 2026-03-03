"""
Gate Counselor — pre-action advisory voice mode.

The Gate Counselor sits between a turbine convergence observation and a
proposed gate action. It evaluates the action context and recommends
PROCEED or DEFER in a single structured response.

This is the highest-stakes voice mode: its output is seen by the operator
before the turbine acts under a SIGNAL gate, and by the GateAuthority log.

Contract:
  - First word MUST be exactly one of: PROCEED, DEFER
  - Followed by exactly one sentence of justification.
  - No additional output. VoiceGuardViolation raised if format is wrong.

PROCEED  = the evidence supports acting now.
DEFER    = insufficient evidence, conditions not yet met, or risk too high.

The Gate Counselor does NOT have authority. It advises. The GateAuthority
makes the final call. The counselor's recommendation is logged alongside
the TurbineAction outcome.

Usage:
    from rhythm_os.voice.gate_counselor import counsel

    result = counsel(action_context={
        "action_type": "SIGNAL",
        "gate_id": "gate-001",
        "convergence_trigger": "convergence:natural,system",
        "domain_pair": "natural+system",
        "classifier_verdict": "LAG",
        "confidence": 0.82,
        "observation_count": 47,
    })
    print(result.recommendation)  # "PROCEED"
    print(result.justification)   # "The natural domain has led..."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Optional

from rhythm_os.voice.guards import extract_verdict_and_rationale

DEFAULT_MODEL = "qwen2.5:7b"

_VALID_RECOMMENDATIONS: FrozenSet[str] = frozenset({"PROCEED", "DEFER"})

_COUNSELOR_INSTRUCTION = """\
You are the Gate Counselor.

A turbine has proposed an action. Advise whether to proceed or defer.
Your response must follow this exact format:

  VERDICT One sentence of justification.

Where VERDICT is exactly one of: PROCEED, DEFER

Definitions:
  PROCEED  The evidence supports acting now. Convergence is confirmed and conditions are met.
  DEFER    Insufficient evidence, unclear pattern, or risk outweighs benefit.

No other output. No markdown. No explanation before the verdict.
"""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounselorResult:
    """
    Output of the Gate Counselor voice mode.

    recommendation  PROCEED | DEFER
    justification   One sentence of justification.
    raw             Raw LLM output before guard parsing.
    """

    recommendation: str
    justification: str
    raw: str


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_counselor_prompt(action_context: Dict[str, Any]) -> str:
    """
    Build the full prompt for the Gate Counselor from an action context dict.

    Typical keys:
      action_type          str  e.g. "SIGNAL"
      gate_id              str
      convergence_trigger  str  e.g. "convergence:natural,system"
      domain_pair          str  e.g. "natural+system"
      classifier_verdict   str  NOISE | COUPLING | LAG
      confidence           float
      observation_count    int
    """
    lines = [_COUNSELOR_INSTRUCTION, "", "Proposed action context:"]
    for key, value in action_context.items():
        lines.append(f"  {key}: {value}")
    lines.append("\nAdvise:")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# counsel
# ---------------------------------------------------------------------------


def counsel(
    action_context: Dict[str, Any],
    *,
    model: str = DEFAULT_MODEL,
    generate_fn: Optional[Callable[[str], str]] = None,
) -> CounselorResult:
    """
    Advise whether the turbine should proceed with a proposed action.

    Parameters
    ----------
    action_context  Dict describing the proposed action and convergence context.
    model           Ollama model tag (ignored if generate_fn is provided).
    generate_fn     Optional callable (prompt: str) -> str.

    Returns
    -------
    CounselorResult  with .recommendation, .justification, .raw.

    Raises
    ------
    VoiceGuardViolation  If LLM output does not start with PROCEED/DEFER.
    OllamaUnavailable    If Ollama cannot be reached and no generate_fn given.
    OllamaError          If Ollama returns a non-200 status.
    """
    if generate_fn is None:
        from rhythm_os.voice.ollama_client import generate as _gen

        def generate_fn(p: str) -> str:
            return _gen(p, model=model)

    prompt = build_counselor_prompt(action_context)
    raw = generate_fn(prompt)
    recommendation, justification = extract_verdict_and_rationale(
        raw, _VALID_RECOMMENDATIONS
    )
    return CounselorResult(
        recommendation=recommendation,
        justification=justification,
        raw=raw,
    )
