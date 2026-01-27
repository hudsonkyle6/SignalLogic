import json
from pathlib import Path

from ollama_client import generate
from staff_prompt import STAFF_SURVEY_PROMPT
from staff_guard import enforce_staff_survey

FORGE_MATERIAL = """
Forge is currently minimal.
Contains Python files for ollama_client, guards, and test scripts.
No automation or execution beyond manual invocation.
"""


def main():
    prompt = STAFF_SURVEY_PROMPT.format(material=FORGE_MATERIAL)

    raw = generate(
        prompt=prompt,
        model="qwen2.5:7b",
    )

    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError("Invalid JSON from model") from e

    survey = enforce_staff_survey(data)

    print(json.dumps(survey, indent=2))


if __name__ == "__main__":
    main()

