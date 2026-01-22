"""
Shepherd Runtime — Read-Only Loaders
Fail-closed. No mutation. No defaults.
"""

import json
import yaml
from pathlib import Path
from typing import Any


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required file missing: {path}")


def load_json(path: Path) -> dict[str, Any]:
    _require(path)
    raw = path.read_text(encoding="utf-8").strip()

    if not raw:
        raise ValueError(f"Required JSON file is empty: {path}")

    return json.loads(raw)



def load_yaml(path: Path) -> dict[str, Any]:
    _require(path)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
