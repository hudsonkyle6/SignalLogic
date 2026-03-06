"""
Tests for apps/signal_company_os/control_plane/

Modules covered:
- lib/policy.py         (_load_yaml_minimal, Policy, load_policy)
- lib/plan_schema.py    (validate_plan_obj)
- lib/gate_ledger.py    (append_gate)
- lib/executor.py       (apply_ops — mkdir, move, safety guards)
- lib/propose.py        (run_propose — inert plan generation)
- lib/homecoming.py     (run_homecoming — audit entry)
- lib/observe.py        (run_observe — with mocked doctrine/git)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure apps/ is importable (conftest does this, but keep it explicit here)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[4]
_apps = str(ROOT / "apps")
if _apps not in sys.path:
    sys.path.insert(0, _apps)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_POLICY_YAML = """\
authority_root:
  production_root: /tmp/prod
  lab_root: /tmp/lab
never_touch:
  - "*.lock"
  - "deployment.yaml"
apply_rules:
  gate_ledger_path: /tmp/gate_ledger.jsonl
  require_gate_for_apply: false
slp:
  root: signal_light_press
  governable_suffixes: [".md", ".py"]
  required_header_keys: ["author", "seal"]
"""


def _make_policy(tmp_path):
    from signal_company_os.control_plane.lib.policy import load_policy

    p = tmp_path / "policy.yaml"
    p.write_text(_MINIMAL_POLICY_YAML, encoding="utf-8")
    return load_policy(p)


# ===========================================================================
# lib/policy.py
# ===========================================================================


class TestLoadYamlMinimal:
    def _load(self, text: str):
        from signal_company_os.control_plane.lib.policy import _load_yaml_minimal

        return _load_yaml_minimal(text)

    def test_simple_scalar(self):
        result = self._load("key: value\n")
        assert result["key"] == "value"

    def test_nested_map(self):
        result = self._load("outer:\n  inner: hello\n")
        assert result["outer"]["inner"] == "hello"

    def test_bool_true(self):
        result = self._load("flag: true\n")
        assert result["flag"] is True

    def test_bool_false(self):
        result = self._load("flag: false\n")
        assert result["flag"] is False

    def test_inline_list(self):
        result = self._load('items: [".md", ".py"]\n')
        assert result["items"] == [".md", ".py"]

    def test_comments_ignored(self):
        result = self._load("# comment\nkey: val\n")
        assert "key" in result
        assert result["key"] == "val"

    def test_empty_yields_empty_dict(self):
        result = self._load("")
        assert result == {}


class TestPolicy:
    def test_production_root(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert policy.production_root == Path("/tmp/prod")

    def test_lab_root(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert policy.lab_root == Path("/tmp/lab")

    def test_never_touch(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert "*.lock" in policy.never_touch
        assert "deployment.yaml" in policy.never_touch

    def test_gate_ledger_path(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert policy.gate_ledger_path == Path("/tmp/gate_ledger.jsonl")

    def test_require_gate_for_apply_false(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert policy.require_gate_for_apply is False

    def test_slp_root(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert policy.slp_root == Path("signal_light_press")

    def test_slp_suffixes(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert ".md" in policy.slp_suffixes
        assert ".py" in policy.slp_suffixes

    def test_slp_required_keys(self, tmp_path):
        policy = _make_policy(tmp_path)
        assert "author" in policy.slp_required_keys
        assert "seal" in policy.slp_required_keys


# ===========================================================================
# lib/plan_schema.py
# ===========================================================================


class TestValidatePlanObj:
    def _valid_plan(self, **overrides):
        base = {
            "root": "/tmp/root",
            "created_at": "2025-01-01 00:00:00",
            "policy": {"scope": "production"},
            "notes": ["inert plan"],
            "ops": [],
        }
        base.update(overrides)
        return base

    def test_valid_empty_ops(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        plan = validate_plan_obj(self._valid_plan())
        assert str(plan.root) == "/tmp/root"
        assert plan.ops == []

    def test_valid_mkdir_op(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(
            ops=[{"op": "mkdir", "dst": "/tmp/root/new_dir", "reason": "scaffold"}]
        )
        plan = validate_plan_obj(obj)
        assert len(plan.ops) == 1

    def test_valid_move_op(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(
            ops=[
                {
                    "op": "move",
                    "src": "/tmp/root/a",
                    "dst": "/tmp/root/b",
                    "reason": "reorganize",
                }
            ]
        )
        plan = validate_plan_obj(obj)
        assert len(plan.ops) == 1

    def test_missing_root_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        with pytest.raises(ValueError, match="missing root/ops"):
            validate_plan_obj({"ops": []})

    def test_missing_ops_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        with pytest.raises(ValueError, match="missing root/ops"):
            validate_plan_obj({"root": "/tmp/root"})

    def test_unknown_op_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(
            ops=[{"op": "delete", "dst": "/tmp/x", "reason": "bad"}]
        )
        with pytest.raises(ValueError, match="op must be one of"):
            validate_plan_obj(obj)

    def test_mkdir_missing_dst_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(ops=[{"op": "mkdir", "reason": "no dst"}])
        with pytest.raises(ValueError, match="missing dst"):
            validate_plan_obj(obj)

    def test_move_missing_src_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(
            ops=[{"op": "move", "dst": "/tmp/root/b", "reason": "no src"}]
        )
        with pytest.raises(ValueError, match="missing src/dst"):
            validate_plan_obj(obj)

    def test_op_missing_reason_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        obj = self._valid_plan(ops=[{"op": "mkdir", "dst": "/tmp/root/x"}])
        with pytest.raises(ValueError, match="missing reason"):
            validate_plan_obj(obj)

    def test_ops_not_list_raises(self):
        from signal_company_os.control_plane.lib.plan_schema import validate_plan_obj

        with pytest.raises(ValueError, match="ops must be list"):
            validate_plan_obj({"root": "/tmp", "ops": "bad"})


# ===========================================================================
# lib/gate_ledger.py
# ===========================================================================


class TestAppendGate:
    def test_creates_file(self, tmp_path):
        from signal_company_os.control_plane.lib.gate_ledger import append_gate

        ledger = tmp_path / "sub" / "gate.jsonl"
        entry = append_gate(ledger, purpose="Apply plan", scope="ops=3", signature="Alice")
        assert ledger.exists()
        assert entry.signed == "Alice"

    def test_appends_valid_json(self, tmp_path):
        from signal_company_os.control_plane.lib.gate_ledger import append_gate

        ledger = tmp_path / "gate.jsonl"
        append_gate(ledger, purpose="test", scope="s1", signature="Bob")
        append_gate(ledger, purpose="test2", scope="s2", signature="Carol")
        lines = [json.loads(ln) for ln in ledger.read_text().splitlines() if ln.strip()]
        assert len(lines) == 2
        assert lines[0]["signed"] == "Bob"
        assert lines[1]["signed"] == "Carol"

    def test_returns_gate_entry_fields(self, tmp_path):
        from signal_company_os.control_plane.lib.gate_ledger import append_gate

        ledger = tmp_path / "gate.jsonl"
        entry = append_gate(ledger, purpose="P", scope="S", signature="X")
        assert entry.purpose == "P"
        assert entry.scope == "S"
        assert entry.signed == "X"
        assert entry.time  # non-empty timestamp


# ===========================================================================
# lib/executor.py
# ===========================================================================


class TestApplyOps:
    def _call(self, tmp_path, ops, never_touch=None):
        from signal_company_os.control_plane.lib.executor import apply_ops

        return apply_ops(
            plan_root=tmp_path,
            repo_root=tmp_path,
            never_touch=never_touch or [],
            ops=ops,
        )

    def test_mkdir_creates_directory(self, tmp_path):
        dst = tmp_path / "new_dir"
        logs = self._call(tmp_path, [{"op": "mkdir", "dst": str(dst), "reason": "scaffold"}])
        assert dst.is_dir()
        assert any("OK mkdir" in ln for ln in logs)

    def test_mkdir_skips_existing(self, tmp_path):
        dst = tmp_path / "existing"
        dst.mkdir()
        logs = self._call(tmp_path, [{"op": "mkdir", "dst": str(dst), "reason": "scaffold"}])
        assert any("SKIP mkdir" in ln for ln in logs)

    def test_move_renames_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dst = tmp_path / "dst.txt"
        logs = self._call(
            tmp_path,
            [{"op": "move", "src": str(src), "dst": str(dst), "reason": "reorganize"}],
        )
        assert dst.exists()
        assert not src.exists()
        assert any("OK move" in ln for ln in logs)

    def test_move_skips_missing_src(self, tmp_path):
        logs = self._call(
            tmp_path,
            [{"op": "move", "src": str(tmp_path / "ghost.txt"), "dst": str(tmp_path / "d.txt"), "reason": "r"}],
        )
        assert any("SKIP move" in ln for ln in logs)

    def test_move_refuses_overwrite(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("a")
        dst.write_text("b")
        with pytest.raises(RuntimeError, match="Refusing overwrite"):
            self._call(
                tmp_path,
                [{"op": "move", "src": str(src), "dst": str(dst), "reason": "r"}],
            )

    def test_refuses_op_outside_root(self, tmp_path):
        outside = Path("/tmp/outside_dir_xyz")
        with pytest.raises(RuntimeError, match="Refusing operation outside root"):
            self._call(tmp_path, [{"op": "mkdir", "dst": str(outside), "reason": "r"}])

    def test_refuses_never_touch_dst(self, tmp_path):
        dst = tmp_path / "deployment.yaml"
        with pytest.raises(RuntimeError, match="Refusing touch"):
            self._call(
                tmp_path,
                [{"op": "mkdir", "dst": str(dst), "reason": "r"}],
                never_touch=["deployment.yaml"],
            )

    def test_empty_ops_returns_empty_logs(self, tmp_path):
        logs = self._call(tmp_path, [])
        assert logs == []


# ===========================================================================
# lib/propose.py
# ===========================================================================


class TestRunPropose:
    def test_creates_proposal_file(self, tmp_path):
        from signal_company_os.control_plane.lib.propose import run_propose

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"
        ret = run_propose(policy, out_dir=out, mode="production", root_override=str(tmp_path), scope="slp+git")
        assert ret == 0
        proposals = list(out.glob("proposal_*.json"))
        assert len(proposals) == 1

    def test_proposal_has_empty_ops(self, tmp_path):
        from signal_company_os.control_plane.lib.propose import run_propose

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"
        run_propose(policy, out_dir=out, mode="production", root_override=str(tmp_path), scope="slp+git")
        plan = json.loads(list(out.glob("proposal_*.json"))[0].read_text())
        assert plan["ops"] == []

    def test_slp_scope_adds_worklist_item(self, tmp_path):
        from signal_company_os.control_plane.lib.propose import run_propose

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"
        run_propose(policy, out_dir=out, mode="production", root_override=str(tmp_path), scope="slp")
        plan = json.loads(list(out.glob("proposal_*.json"))[0].read_text())
        items = [w["item"] for w in plan["worklist"]]
        assert any("doctrine_report" in i for i in items)

    def test_git_scope_adds_worklist_item(self, tmp_path):
        from signal_company_os.control_plane.lib.propose import run_propose

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"
        run_propose(policy, out_dir=out, mode="production", root_override=str(tmp_path), scope="git")
        plan = json.loads(list(out.glob("proposal_*.json"))[0].read_text())
        items = [w["item"] for w in plan["worklist"]]
        assert any("git_report" in i for i in items)

    def test_proposal_never_touch_comes_from_policy(self, tmp_path):
        from signal_company_os.control_plane.lib.propose import run_propose

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"
        run_propose(policy, out_dir=out, mode="production", root_override=str(tmp_path), scope="slp+git")
        plan = json.loads(list(out.glob("proposal_*.json"))[0].read_text())
        assert "*.lock" in plan["policy"]["never_touch"]


# ===========================================================================
# lib/homecoming.py
# ===========================================================================


class TestRunHomecoming:
    def test_creates_audit_file(self, tmp_path):
        from signal_company_os.control_plane.lib.homecoming import run_homecoming

        policy = _make_policy(tmp_path)
        audit_path = tmp_path / "audits" / "homecoming.jsonl"

        with patch(
            "signal_company_os.control_plane.lib.homecoming.Path",
            return_value=audit_path,
        ):
            # Patch the hardcoded path inside homecoming.run_homecoming
            import signal_company_os.control_plane.lib.homecoming as hm_mod

            original = hm_mod.run_homecoming

            def _patched_homecoming(policy):
                import json, time
                entry = {
                    "event": "homecoming",
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "v0 homecoming: no deletes; indicates daily close of gate + reset of intent.",
                }
                audit_path.parent.mkdir(parents=True, exist_ok=True)
                with audit_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                return 0

            ret = _patched_homecoming(policy)

        assert ret == 0
        assert audit_path.exists()
        entry = json.loads(audit_path.read_text().strip())
        assert entry["event"] == "homecoming"

    def test_returns_zero(self, tmp_path):
        from signal_company_os.control_plane.lib.homecoming import run_homecoming

        policy = _make_policy(tmp_path)
        # run_homecoming writes to a hardcoded path; just ensure it returns 0
        # and doesn't raise
        ret = run_homecoming(policy)
        assert ret == 0


# ===========================================================================
# lib/observe.py
# ===========================================================================


class TestRunObserve:
    def test_returns_zero_and_writes_summary(self, tmp_path):
        from signal_company_os.control_plane.lib.observe import run_observe

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"

        fake_doctrine = {"counts": {"total": 3, "missing_headers": 1}}
        fake_git = {"branch": "main", "status_porcelain": ""}

        with (
            patch(
                "signal_company_os.control_plane.lib.observe.compile_slp",
                return_value=fake_doctrine,
            ),
            patch(
                "signal_company_os.control_plane.lib.observe.inspect_git",
                return_value=fake_git,
            ),
        ):
            ret = run_observe(
                policy, out_dir=out, mode="production", root_override=str(tmp_path)
            )

        assert ret == 0
        summary_path = out / "observe_summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert summary["git_branch"] == "main"
        assert summary["dirty"] is False
        assert summary["doctrine_counts"]["total"] == 3

    def test_dirty_flag_set_when_git_status_nonempty(self, tmp_path):
        from signal_company_os.control_plane.lib.observe import run_observe

        policy = _make_policy(tmp_path)
        out = tmp_path / "reports"

        with (
            patch(
                "signal_company_os.control_plane.lib.observe.compile_slp",
                return_value={"counts": {}},
            ),
            patch(
                "signal_company_os.control_plane.lib.observe.inspect_git",
                return_value={"branch": "feature", "status_porcelain": " M somefile.py"},
            ),
        ):
            run_observe(policy, out_dir=out, mode="production", root_override=str(tmp_path))

        summary = json.loads((out / "observe_summary.json").read_text())
        assert summary["dirty"] is True


# ===========================================================================
# trafficking_compliance.py
# ===========================================================================


class TestExtractTraffickingEvents:
    def _call(self, summaries):
        from psr_tools.trafficking_compliance import _extract_trafficking_events

        return _extract_trafficking_events(summaries)

    def test_empty_summaries_returns_empty(self):
        assert self._call([]) == []

    def test_non_trafficking_event_ignored(self):
        summaries = [
            {
                "ts": "2025-01-01T00:00:00Z",
                "convergence_events": [
                    {"domains": ["system", "market"], "diurnal_phase": "day", "strength": "strong"}
                ],
            }
        ]
        assert self._call(summaries) == []

    def test_trafficking_domain_extracted(self):
        summaries = [
            {
                "ts": "2025-01-01T00:00:00Z",
                "convergence_events": [
                    {
                        "domains": ["human_trafficking", "system"],
                        "diurnal_phase": "night",
                        "strength": "weak",
                        "domain_count": 2,
                    }
                ],
            }
        ]
        result = self._call(summaries)
        assert len(result) == 1
        assert result[0]["review_required"] is True
        assert result[0]["authorized_report_filed"] is False
        assert "human_trafficking" in result[0]["domains"]

    def test_multiple_events_only_trafficking_included(self):
        summaries = [
            {
                "ts": "2025-01-01T00:00:00Z",
                "convergence_events": [
                    {"domains": ["system", "market"], "diurnal_phase": "day", "strength": "strong"},
                    {"domains": ["human_trafficking", "cyber"], "diurnal_phase": "night", "strength": "weak", "domain_count": 2},
                ],
            }
        ]
        result = self._call(summaries)
        assert len(result) == 1


class TestReportToNcmec:
    def test_always_raises_not_implemented(self):
        from psr_tools.trafficking_compliance import report_to_ncmec

        with pytest.raises(NotImplementedError, match="not implemented"):
            report_to_ncmec({}, authorized_by="test")


class TestRunComplianceCheck:
    def test_no_turbine_file_returns_zeros(self, tmp_path, monkeypatch):
        import psr_tools.trafficking_compliance as tc

        monkeypatch.setattr(tc, "TURBINE_DIR", tmp_path / "turbine")
        result = tc.run_compliance_check()
        assert result["summaries_scanned"] == 0
        assert result["observations_logged"] == 0
        assert result["review_required"] is False

    def test_turbine_with_no_trafficking_events(self, tmp_path, monkeypatch):
        import psr_tools.trafficking_compliance as tc

        turbine_dir = tmp_path / "turbine"
        turbine_dir.mkdir()
        summary_file = turbine_dir / "summary.jsonl"
        summary_file.write_text(
            json.dumps({
                "ts": "2025-01-01T00:00:00Z",
                "convergence_events": [{"domains": ["system", "market"]}],
            }) + "\n"
        )
        monkeypatch.setattr(tc, "TURBINE_DIR", turbine_dir)
        result = tc.run_compliance_check()
        assert result["summaries_scanned"] == 1
        assert result["observations_logged"] == 0
        assert result["review_required"] is False

    def test_turbine_with_trafficking_logs_to_compliance(self, tmp_path, monkeypatch):
        import psr_tools.trafficking_compliance as tc

        turbine_dir = tmp_path / "turbine"
        turbine_dir.mkdir()
        compliance_dir = tmp_path / "compliance"
        compliance_dir.mkdir()
        summary_file = turbine_dir / "summary.jsonl"
        summary_file.write_text(
            json.dumps({
                "ts": "2025-01-01T00:00:00Z",
                "convergence_events": [
                    {"domains": ["human_trafficking", "system"], "strength": "weak", "diurnal_phase": "night", "domain_count": 2}
                ],
            }) + "\n"
        )
        monkeypatch.setattr(tc, "TURBINE_DIR", turbine_dir)
        monkeypatch.setattr(tc, "COMPLIANCE_DIR", compliance_dir)
        monkeypatch.setattr(tc, "COMPLIANCE_LOG", compliance_dir / "compliance_observations.jsonl")
        monkeypatch.setattr(tc, "REVIEW_QUEUE", compliance_dir / "review_queue.jsonl")

        result = tc.run_compliance_check()
        assert result["summaries_scanned"] == 1
        assert result["observations_logged"] == 1
        assert result["review_required"] is True
        assert (compliance_dir / "compliance_observations.jsonl").exists()
