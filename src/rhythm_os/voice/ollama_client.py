"""
Ollama client for rhythm_os voice layer.

Thin wrapper around the Ollama REST API (`/api/generate`).
Built from the archive prototype at:
  signal_light_press/archive/legacy/.../llm_access_code/ollama_client.py

Two exception types separate infrastructure failure from API errors:
  OllamaUnavailable — Ollama server not reachable (connection / timeout)
  OllamaError       — Server responded but with an error status

The `generate()` function is the only public interface. It is designed
to be injectable in all voice modules so tests can run without Ollama.

Default model: qwen2.5:7b (pulled locally).
Default temperature: 0.2 (deterministic enough for structured output).
"""

from __future__ import annotations

import os
import requests

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_DEFAULT_URL = f"{_OLLAMA_HOST}/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OllamaError(Exception):
    """Ollama responded with a non-200 status code."""


class OllamaUnavailable(OllamaError):
    """Ollama server is not reachable (connection refused or timeout)."""


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    top_p: float = 0.9,
    num_ctx: int = 4096,
    timeout: int = 120,
    base_url: str = OLLAMA_DEFAULT_URL,
) -> str:
    """
    Generate a response from the local Ollama server.

    Parameters
    ----------
    prompt       Full prompt text (system instruction + user content combined)
    model        Ollama model tag, e.g. "qwen2.5:7b"
    temperature  Sampling temperature (0.0 = deterministic, 1.0 = creative)
    top_p        Nucleus sampling cutoff
    num_ctx      Context window in tokens
    timeout      HTTP request timeout in seconds
    base_url     Ollama API endpoint (override for testing)

    Returns
    -------
    str  The model's raw response text.

    Raises
    ------
    OllamaUnavailable  If the server cannot be reached.
    OllamaError        If the server returns a non-200 response.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": num_ctx,
        },
    }

    try:
        response = requests.post(base_url, json=payload, timeout=timeout)
    except requests.ConnectionError as exc:
        raise OllamaUnavailable(f"cannot reach Ollama at {base_url}: {exc}") from exc
    except requests.Timeout as exc:
        raise OllamaUnavailable(f"timeout waiting for Ollama at {base_url}") from exc

    if response.status_code != 200:
        raise OllamaError(f"HTTP {response.status_code}: {response.text}")

    return response.json()["response"]
