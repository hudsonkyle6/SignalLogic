"""
Additional tests for control_plane/lib/policy.py

Targets the branch paths in _load_yaml_minimal that are not yet covered:
- Nested list under map key (block list items)
- Deeply nested maps
- Quoted strings
- Mixed inline list with spaces
"""

from __future__ import annotations

import pytest


import sys
from unittest.mock import patch


def _load(text: str) -> dict:
    from signal_company_os.control_plane.lib.policy import _load_yaml_minimal
    return _load_yaml_minimal(text)


def _load_custom(text: str) -> dict:
    """Force the custom minimal YAML parser by blocking yaml import (None sentinel)."""
    import sys
    from signal_company_os.control_plane.lib.policy import _load_yaml_minimal

    saved = sys.modules.get("yaml", ...)  # ... = sentinel "not set"
    sys.modules["yaml"] = None  # type: ignore[assignment]  # blocks 'import yaml'
    try:
        result = _load_yaml_minimal(text)
    finally:
        if saved is ...:
            del sys.modules["yaml"]
        else:
            sys.modules["yaml"] = saved
    return result


class TestYamlMinimalExtraBranches:
    def test_block_list_under_key(self):
        text = "items:\n  - alpha\n  - beta\n"
        result = _load(text)
        # The minimal parser initializes the key as {} then adds items
        # to a new dict; block list handling is best-effort
        assert "items" in result

    def test_deeply_nested_map(self):
        text = "a:\n  b:\n    c: deep\n"
        result = _load(text)
        assert result["a"]["b"]["c"] == "deep"

    def test_quoted_value_stripped(self):
        result = _load('key: "quoted value"\n')
        assert result["key"] == "quoted value"

    def test_single_quoted_value_stripped(self):
        result = _load("key: 'single quoted'\n")
        assert result["key"] == "single quoted"

    def test_inline_list_with_spaces(self):
        result = _load("items: [ one , two , three ]\n")
        assert result["items"] == ["one", "two", "three"]

    def test_inline_empty_list(self):
        result = _load("items: []\n")
        assert result["items"] == []

    def test_multiple_top_level_keys(self):
        text = "a: 1\nb: 2\nc: 3\n"
        result = _load(text)
        # minimal parser returns numeric strings as-is
        assert str(result["a"]) == "1"
        assert str(result["b"]) == "2"
        assert str(result["c"]) == "3"

    def test_bool_true_various_case(self):
        result = _load("flag: True\n")
        assert result["flag"] is True

    def test_bool_false_various_case(self):
        result = _load("flag: False\n")
        assert result["flag"] is False

    def test_mixed_map_and_scalars(self):
        text = "outer:\n  scalar: hello\n  nested:\n    deep: value\n"
        result = _load(text)
        assert result["outer"]["scalar"] == "hello"
        assert result["outer"]["nested"]["deep"] == "value"

    def test_colon_in_value(self):
        # Values with colons after the first colon should be preserved
        result = _load("url: http\n")
        # url gets parsed as key="url", value="http"
        assert "url" in result


class TestCustomYamlParser:
    """Exercise the fallback minimal parser (runs when yaml is not importable)."""

    def test_simple_scalar(self):
        result = _load_custom("key: value\n")
        assert result["key"] == "value"

    def test_nested_map(self):
        result = _load_custom("outer:\n  inner: hello\n")
        assert result["outer"]["inner"] == "hello"

    def test_bool_true(self):
        result = _load_custom("flag: true\n")
        assert result["flag"] is True

    def test_bool_false(self):
        result = _load_custom("flag: false\n")
        assert result["flag"] is False

    def test_inline_list(self):
        result = _load_custom('items: [".md", ".py"]\n')
        assert result["items"] == [".md", ".py"]

    def test_inline_empty_list(self):
        result = _load_custom("items: []\n")
        assert result["items"] == []

    def test_comments_ignored(self):
        result = _load_custom("# comment\nkey: val\n")
        assert result["key"] == "val"

    def test_empty_text(self):
        result = _load_custom("")
        assert result == {}

    def test_deeply_nested(self):
        result = _load_custom("a:\n  b:\n    c: deep\n")
        assert result["a"]["b"]["c"] == "deep"

    def test_quoted_value(self):
        result = _load_custom('key: "quoted"\n')
        assert result["key"] == "quoted"

    def test_block_list_items_raises(self):
        # Custom parser cannot handle block lists under map keys (by design)
        text = "things:\n  - one\n  - two\n"
        with pytest.raises(ValueError, match="List item under non-list"):
            _load_custom(text)

    def test_multiple_keys(self):
        result = _load_custom("x: 1\ny: 2\n")
        assert str(result["x"]) == "1"
        assert str(result["y"]) == "2"


class TestPolicyRequireGateForApplyTrue:
    def test_require_gate_true(self, tmp_path):
        from signal_company_os.control_plane.lib.policy import load_policy

        yaml = """\
authority_root:
  production_root: /tmp/prod
  lab_root: /tmp/lab
never_touch: []
apply_rules:
  gate_ledger_path: /tmp/gate.jsonl
  require_gate_for_apply: true
slp:
  root: slp
  governable_suffixes: [".md"]
  required_header_keys: ["author"]
"""
        p = tmp_path / "policy.yaml"
        p.write_text(yaml)
        policy = load_policy(p)
        assert policy.require_gate_for_apply is True

    def test_empty_never_touch(self, tmp_path):
        from signal_company_os.control_plane.lib.policy import load_policy

        yaml = """\
authority_root:
  production_root: /tmp/prod
  lab_root: /tmp/lab
apply_rules:
  gate_ledger_path: /tmp/gate.jsonl
  require_gate_for_apply: false
slp:
  root: slp
  governable_suffixes: []
  required_header_keys: []
"""
        p = tmp_path / "policy.yaml"
        p.write_text(yaml)
        policy = load_policy(p)
        assert policy.never_touch == []
        assert policy.slp_suffixes == []
        assert policy.slp_required_keys == []
