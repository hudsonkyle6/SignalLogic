from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


def _load_yaml_minimal(text: str) -> Dict[str, Any]:
    """
    Minimal YAML loader (no deps). Supports only key: value, nested via indentation,
    and simple lists. If PyYAML is installed, we will use it instead.
    """
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        pass

    # Very small parser for our specific policy.yaml structure
    root: Dict[str, Any] = {}
    stack: List[tuple[int, Any]] = [(0, root)]

    def set_kv(container: Any, k: str, v: Any):
        if isinstance(container, dict):
            container[k] = v
        else:
            raise ValueError("Invalid container for kv")

    lines = [
        ln.rstrip("\n")
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    for ln in lines:
        indent = len(ln) - len(ln.lstrip(" "))
        while stack and indent < stack[-1][0]:
            stack.pop()

        cur = stack[-1][1]

        if ln.lstrip().startswith("- "):
            item = ln.lstrip()[2:].strip().strip('"').strip("'")
            if isinstance(cur, list):
                cur.append(item)
            else:
                raise ValueError("List item under non-list")
            continue

        if ":" in ln:
            k, rest = ln.lstrip().split(":", 1)
            k = k.strip()
            rest = rest.strip()
            if rest == "":
                # start nested map or list inferred later
                new_obj: Any = {}
                set_kv(cur, k, new_obj)
                stack.append((indent + 2, new_obj))
            else:
                # parse scalar or inline list
                if rest.startswith("[") and rest.endswith("]"):
                    inner = rest[1:-1].strip()
                    if not inner:
                        v = []
                    else:
                        parts = [
                            p.strip().strip('"').strip("'") for p in inner.split(",")
                        ]
                        v = parts
                else:
                    v = rest.strip('"').strip("'")
                    if v.lower() == "true":
                        v = True
                    elif v.lower() == "false":
                        v = False
                set_kv(cur, k, v)
            continue

    # Fix any dicts that should be lists if policy defines them that way (we keep it simple)
    return root


@dataclass
class Policy:
    raw: Dict[str, Any]

    @property
    def production_root(self) -> Path:
        return Path(self.raw["authority_root"]["production_root"])

    @property
    def lab_root(self) -> Path:
        return Path(self.raw["authority_root"]["lab_root"])

    @property
    def never_touch(self) -> List[str]:
        return list(self.raw.get("never_touch", []))

    @property
    def gate_ledger_path(self) -> Path:
        return Path(self.raw["apply_rules"]["gate_ledger_path"])

    @property
    def require_gate_for_apply(self) -> bool:
        return bool(self.raw["apply_rules"]["require_gate_for_apply"])

    @property
    def slp_root(self) -> Path:
        return Path(self.raw["slp"]["root"])

    @property
    def slp_suffixes(self) -> List[str]:
        return list(self.raw["slp"]["governable_suffixes"])

    @property
    def slp_required_keys(self) -> List[str]:
        return list(self.raw["slp"]["required_header_keys"])


def load_policy(path: Path) -> Policy:
    text = path.read_text(encoding="utf-8")
    raw = _load_yaml_minimal(text)
    return Policy(raw=raw)
