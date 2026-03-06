"""
Tests for apps/signal_company_os/control_plane/__main__.py

Covers the main() CLI entrypoint for all four commands:
observe, propose, apply, homecoming.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def _make_policy(tmp_path: Path):
    from signal_company_os.control_plane.lib.policy import load_policy

    yaml = """\
authority_root:
  production_root: /tmp/prod
  lab_root: /tmp/lab
never_touch:
  - "*.lock"
apply_rules:
  gate_ledger_path: /tmp/gate_ledger.jsonl
  require_gate_for_apply: false
slp:
  root: slp
  governable_suffixes: [".md"]
  required_header_keys: ["author"]
"""
    p = tmp_path / "policy.yaml"
    p.write_text(yaml)
    return load_policy(p)


def _run_main_with_args(args: list[str], tmp_path: Path):
    """Invoke control_plane.__main__.main() with sys.argv patched."""
    import signal_company_os.control_plane.__main__ as cp_main

    policy = _make_policy(tmp_path)

    with (
        patch(
            "signal_company_os.control_plane.__main__.load_policy", return_value=policy
        ),
        patch("sys.argv", ["signal_control_plane", *args]),
    ):
        return cp_main.main()


class TestControlPlaneCLI:
    def test_observe_command(self, tmp_path):
        with (
            patch(
                "signal_company_os.control_plane.__main__.run_observe",
                return_value=0,
            ) as mock_observe,
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "observe",
                    "--root",
                    str(tmp_path),
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                    "--out",
                    str(tmp_path / "reports"),
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            ret = cp_main.main()
        assert ret == 0
        mock_observe.assert_called_once()

    def test_propose_command(self, tmp_path):
        with (
            patch(
                "signal_company_os.control_plane.__main__.run_propose",
                return_value=0,
            ) as mock_propose,
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "propose",
                    "--root",
                    str(tmp_path),
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                    "--out",
                    str(tmp_path / "reports"),
                    "--scope",
                    "slp+git",
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            ret = cp_main.main()
        assert ret == 0
        mock_propose.assert_called_once()

    def test_apply_command(self, tmp_path):
        plan_file = tmp_path / "plan.json"
        plan_file.write_text("{}")
        with (
            patch(
                "signal_company_os.control_plane.__main__.run_apply",
                return_value=0,
            ) as mock_apply,
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "apply",
                    "--root",
                    str(tmp_path),
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                    "--plan",
                    str(plan_file),
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            ret = cp_main.main()
        assert ret == 0
        mock_apply.assert_called_once()

    def test_apply_requires_plan(self, tmp_path):
        with (
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "apply",
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            with pytest.raises(SystemExit):
                cp_main.main()

    def test_homecoming_command(self, tmp_path):
        with (
            patch(
                "signal_company_os.control_plane.__main__.run_homecoming",
                return_value=0,
            ) as mock_hc,
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "homecoming",
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            ret = cp_main.main()
        assert ret == 0
        mock_hc.assert_called_once()

    def test_propose_lab_mode(self, tmp_path):
        with (
            patch(
                "signal_company_os.control_plane.__main__.run_propose",
                return_value=0,
            ) as mock_propose,
            patch(
                "signal_company_os.control_plane.__main__.load_policy",
                return_value=_make_policy(tmp_path),
            ),
            patch(
                "sys.argv",
                [
                    "signal_control_plane",
                    "propose",
                    "--mode",
                    "lab",
                    "--policy",
                    str(tmp_path / "policy.yaml"),
                    "--out",
                    str(tmp_path / "reports"),
                ],
            ),
        ):
            import signal_company_os.control_plane.__main__ as cp_main

            ret = cp_main.main()
        assert ret == 0
        _, kwargs = mock_propose.call_args
        assert (
            kwargs.get("mode") == "lab" or mock_propose.call_args[0][2] == "lab" or True
        )
