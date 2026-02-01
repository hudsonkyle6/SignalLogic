####run_proposals.py
import json
from uuid import uuid4

from ollama_client import generate
from proposal_prompt import PROPOSAL_PROMPT
from proposal_guard import enforce_proposal_report


FORGE_MATERIAL = """
Forge currently includes:
- ollama_client for LLM access
- staff survey pipeline
- no persistence layer yet
- no execution or automation enabled
"""


def main():
    # 1. Generate proposal text
    raw = generate(
        prompt=PROPOSAL_PROMPT.format(material=FORGE_MATERIAL),
        model="qwen2.5:7b",
    )

    # 2. Parse JSON
    try:
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError("Invalid JSON from model") from e

    # 3. Enforce schema (staff authority ends here)
    report = enforce_proposal_report(data)

    # 4. SYSTEM AUTHORITY: assign proposal IDs
    for proposal in report["proposals"]:
        proposal["proposal_id"] = str(uuid4())

    # 5. Output (later: persist)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
