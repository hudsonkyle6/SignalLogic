"""
Tests for control_plane lib: doctrine.py and git_inspect.py

Modules covered:
- lib/doctrine.py   (sha256_file, parse_header, broken_links, compile_slp)
- lib/git_inspect.py (run_git, inspect_git)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# doctrine.py — sha256_file
# ===========================================================================


class TestSha256File:
    def test_returns_hex_string(self, tmp_path):
        from signal_company_os.control_plane.lib.doctrine import sha256_file

        f = tmp_path / "test.txt"
        f.write_bytes(b"hello")
        result = sha256_file(f)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_different_content_different_hash(self, tmp_path):
        from signal_company_os.control_plane.lib.doctrine import sha256_file

        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_bytes(b"hello")
        b.write_bytes(b"world")
        assert sha256_file(a) != sha256_file(b)

    def test_same_content_same_hash(self, tmp_path):
        from signal_company_os.control_plane.lib.doctrine import sha256_file

        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_bytes(b"identical")
        b.write_bytes(b"identical")
        assert sha256_file(a) == sha256_file(b)

    def test_empty_file(self, tmp_path):
        from signal_company_os.control_plane.lib.doctrine import sha256_file

        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        result = sha256_file(f)
        # SHA256 of empty string is well-known
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ===========================================================================
# doctrine.py — parse_header
# ===========================================================================


class TestParseHeader:
    def _call(self, text, required_keys):
        from signal_company_os.control_plane.lib.doctrine import parse_header

        return parse_header(text, required_keys)

    def test_all_keys_present(self):
        text = "author: Alice\nseal: 2025-01\n\nBody here."
        ok, found, missing = self._call(text, ["author", "seal"])
        assert ok is True
        assert found["author"] == "Alice"
        assert found["seal"] == "2025-01"
        assert missing == []

    def test_missing_key(self):
        text = "author: Alice\n\nBody here."
        ok, found, missing = self._call(text, ["author", "seal"])
        assert ok is False
        assert "seal" in missing

    def test_no_required_keys(self):
        text = "anything: here\n"
        ok, found, missing = self._call(text, [])
        assert ok is True
        assert missing == []

    def test_stops_at_heading_when_found_nonempty(self):
        text = "author: Alice\n# Section\nmore: content\n"
        ok, found, missing = self._call(text, ["author"])
        # stops at # when found is non-empty
        assert "more" not in found
        assert ok is True

    def test_three_blanks_stops_parsing(self):
        text = "author: Alice\n\n\n\nskip: this\n"
        ok, found, missing = self._call(text, ["author"])
        assert ok is True
        assert "skip" not in found

    def test_empty_text_missing_all(self):
        ok, found, missing = self._call("", ["author", "seal"])
        assert ok is False
        assert set(missing) == {"author", "seal"}

    def test_extra_keys_parsed(self):
        text = "author: Bob\nseal: 2025-02\nversion: 1.0\n"
        ok, found, missing = self._call(text, ["author", "seal"])
        assert ok is True
        assert found["version"] == "1.0"


# ===========================================================================
# doctrine.py — broken_links
# ===========================================================================


class TestBrokenLinks:
    def _call(self, md_path, text):
        from signal_company_os.control_plane.lib.doctrine import broken_links

        return broken_links(md_path, text)

    def test_external_links_ignored(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        result = self._call(md, "[link](https://example.com) [mail](mailto:a@b.com)")
        assert result == []

    def test_anchor_links_ignored(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        result = self._call(md, "[anchor](#section)")
        assert result == []

    def test_existing_local_file_not_broken(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        target = tmp_path / "other.md"
        target.write_text("")
        result = self._call(md, "[see](other.md)")
        assert result == []

    def test_missing_local_file_is_broken(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        result = self._call(md, "[missing](ghost.md)")
        assert len(result) == 1
        assert result[0]["target"] == "ghost.md"

    def test_anchor_stripped_from_local_link(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        existing = tmp_path / "real.md"
        existing.write_text("")
        result = self._call(md, "[link](real.md#anchor)")
        assert result == []

    def test_empty_target_ignored(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        # after stripping anchor from "#" we get empty target — should be ignored
        result = self._call(md, "[link](#)")
        assert result == []


# ===========================================================================
# doctrine.py — compile_slp
# ===========================================================================


class TestCompileSlp:
    def _call(self, slp_root, tmp_path, suffixes=None, required_keys=None):
        from signal_company_os.control_plane.lib.doctrine import compile_slp

        out = tmp_path / "out"
        return compile_slp(
            slp_root=slp_root,
            suffixes=suffixes or [".md", ".py"],
            required_keys=required_keys or ["author"],
            out_dir=out,
        ), out

    def test_empty_dir_produces_zero_counts(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        report, out = self._call(slp, tmp_path)
        assert report["counts"]["files"] == 0
        assert report["counts"]["missing_headers"] == 0

    def test_writes_doctrine_index_json(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        _, out = self._call(slp, tmp_path)
        assert (out / "doctrine_index.json").exists()

    def test_writes_doctrine_report_md(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        _, out = self._call(slp, tmp_path)
        assert (out / "doctrine_report.md").exists()

    def test_file_with_header_counted(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        (slp / "doc.md").write_text("author: Alice\n\nContent.")
        report, _ = self._call(slp, tmp_path)
        assert report["counts"]["files"] == 1
        assert report["counts"]["missing_headers"] == 0

    def test_file_missing_header_counted(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        (slp / "doc.md").write_text("No header here.")
        report, _ = self._call(slp, tmp_path)
        assert report["counts"]["missing_headers"] == 1

    def test_duplicate_files_detected(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        content = "author: Alice\n\nIdentical content."
        (slp / "a.md").write_text(content)
        (slp / "b.md").write_text(content)
        report, _ = self._call(slp, tmp_path)
        assert report["counts"]["duplicate_sets"] == 1

    def test_broken_link_in_md_counted(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        (slp / "doc.md").write_text("author: Alice\n\n[broken](ghost.md)")
        report, _ = self._call(slp, tmp_path)
        assert report["counts"]["broken_links"] == 1

    def test_non_matching_suffix_ignored(self, tmp_path):
        slp = tmp_path / "slp"
        slp.mkdir()
        (slp / "data.csv").write_text("col1,col2")
        report, _ = self._call(slp, tmp_path, suffixes=[".md"])
        assert report["counts"]["files"] == 0


# ===========================================================================
# git_inspect.py — run_git
# ===========================================================================


class TestRunGit:
    def test_returns_stdout_on_success(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import run_git

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = run_git(["branch", "--show-current"], tmp_path)
        assert result == "main"

    def test_returns_error_string_on_failure(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import run_git

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repo"
        with patch("subprocess.run", return_value=mock_result):
            result = run_git(["status"], tmp_path)
        assert result.startswith("[GIT ERROR]")
        assert "not a git repo" in result


# ===========================================================================
# git_inspect.py — inspect_git
# ===========================================================================


class TestInspectGit:
    def _mock_run_git(self, mapping: dict):
        """Return a mock for run_git that uses first-arg keyword from cmd."""

        def _side_effect(cmd, cwd):
            for key, val in mapping.items():
                if key in cmd:
                    return val
            return ""

        return _side_effect

    def test_creates_git_report_json(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import inspect_git

        with patch(
            "signal_company_os.control_plane.lib.git_inspect.run_git",
            return_value="",
        ):
            inspect_git(repo_root=tmp_path, out_dir=tmp_path / "out")

        assert (tmp_path / "out" / "git_report.json").exists()

    def test_creates_git_report_md(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import inspect_git

        with patch(
            "signal_company_os.control_plane.lib.git_inspect.run_git",
            return_value="",
        ):
            inspect_git(repo_root=tmp_path, out_dir=tmp_path / "out")

        assert (tmp_path / "out" / "git_report.md").exists()

    def test_returns_data_dict(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import inspect_git

        with patch(
            "signal_company_os.control_plane.lib.git_inspect.run_git",
            return_value="main",
        ):
            data = inspect_git(repo_root=tmp_path, out_dir=tmp_path / "out")

        assert isinstance(data, dict)
        assert "branch" in data
        assert "status_porcelain" in data

    def test_report_json_valid(self, tmp_path):
        from signal_company_os.control_plane.lib.git_inspect import inspect_git

        with patch(
            "signal_company_os.control_plane.lib.git_inspect.run_git",
            return_value="feature-branch",
        ):
            inspect_git(repo_root=tmp_path, out_dir=tmp_path / "out")

        report = json.loads((tmp_path / "out" / "git_report.json").read_text())
        assert report["branch"] == "feature-branch"
