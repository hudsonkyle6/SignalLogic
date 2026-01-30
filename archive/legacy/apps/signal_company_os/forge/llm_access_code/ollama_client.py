import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

class OllamaError(Exception):
    pass


def generate(
    prompt: str,
    *,
    model: str,
    temperature: float = 0.2,
    top_p: float = 0.9,
    num_ctx: int = 4096,
    timeout: int = 120,
) -> str:
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

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=timeout,
    )

    if response.status_code != 200:
        raise OllamaError(response.text)

    return response.json()["response"]
