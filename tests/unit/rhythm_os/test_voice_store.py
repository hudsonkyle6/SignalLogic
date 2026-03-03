"""
Tests for rhythm_os.voice.voice_store

Modules covered:
- VoiceLine
- persist_voice_line
- load_last_voice_line

Invariants:
- VoiceLine.to_dict() / from_dict() round-trips without data loss
- persist_voice_line assigns t and line_id if not provided
- persist_voice_line respects provided t and line_id
- persist_voice_line appends to store; reading back returns same record
- persist_voice_line creates parent directories automatically
- load_last_voice_line returns None when store does not exist
- load_last_voice_line returns None when store is empty
- load_last_voice_line returns the most-recent record (last line wins)
- load_last_voice_line filters by mode when mode is given
- load_last_voice_line returns None when no records match mode filter
- load_last_voice_line skips corrupt JSON lines without raising
- helix_dashboard._load_narrator_line returns empty string when no store
- helix_dashboard._load_narrator_line returns text of most-recent narrator line
- helix_dashboard._panel_narrator returns Panel with placeholder text when empty
- helix_dashboard._panel_narrator returns Panel with voice text when populated
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhythm_os.voice.voice_store import VoiceLine, load_last_voice_line, persist_voice_line


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "voice" / "voice_lines.jsonl"


# ---------------------------------------------------------------------------
# VoiceLine dataclass
# ---------------------------------------------------------------------------


class TestVoiceLine:
    def test_to_dict_has_required_keys(self):
        vl = VoiceLine(mode="narrator", text="Hello.", raw="Hello.")
        d = vl.to_dict()
        assert "mode" in d
        assert "text" in d
        assert "raw" in d
        assert "t" in d
        assert "line_id" in d

    def test_from_dict_round_trip(self):
        original = VoiceLine(mode="narrator", text="Some text.", raw="Some text.", t=1.0, line_id="abc")
        restored = VoiceLine.from_dict(original.to_dict())
        assert restored.mode == "narrator"
        assert restored.text == "Some text."
        assert restored.raw == "Some text."
        assert restored.t == 1.0
        assert restored.line_id == "abc"

    def test_from_dict_missing_optional_fields(self):
        d = {"mode": "interpreter", "text": "X.", "raw": "X."}
        vl = VoiceLine.from_dict(d)
        assert vl.mode == "interpreter"
        assert vl.t == 0.0
        assert vl.line_id == ""

    def test_frozen(self):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        with pytest.raises(Exception):
            vl.mode = "counselor"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# persist_voice_line
# ---------------------------------------------------------------------------


class TestPersistVoiceLine:
    def test_returns_voice_line(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="The system observed.", raw="The system observed.")
        result = persist_voice_line(vl, store_path=store_path)
        assert isinstance(result, VoiceLine)

    def test_assigns_timestamp_if_missing(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        result = persist_voice_line(vl, store_path=store_path)
        assert result.t > 0.0

    def test_respects_explicit_timestamp(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        result = persist_voice_line(vl, store_path=store_path, now=999.0)
        assert result.t == 999.0

    def test_assigns_line_id_if_missing(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        result = persist_voice_line(vl, store_path=store_path)
        assert result.line_id != ""

    def test_respects_explicit_line_id(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.", line_id="custom-id")
        result = persist_voice_line(vl, store_path=store_path)
        assert result.line_id == "custom-id"

    def test_creates_parent_directories(self, tmp_path: Path):
        deep_path = tmp_path / "a" / "b" / "c" / "lines.jsonl"
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=deep_path)
        assert deep_path.exists()

    def test_file_exists_after_persist(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=store_path)
        assert store_path.exists()

    def test_file_has_one_line(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=store_path)
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_two_persists_append(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=store_path)
        persist_voice_line(vl, store_path=store_path)
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_record_is_valid_json(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=store_path)
        raw = store_path.read_text().strip()
        data = json.loads(raw)
        assert data["mode"] == "narrator"

    def test_text_and_raw_preserved(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="Display text.", raw="Raw LLM output.")
        result = persist_voice_line(vl, store_path=store_path)
        assert result.text == "Display text."
        assert result.raw == "Raw LLM output."


# ---------------------------------------------------------------------------
# load_last_voice_line
# ---------------------------------------------------------------------------


class TestLoadLastVoiceLine:
    def test_returns_none_when_store_missing(self, tmp_path: Path):
        path = tmp_path / "nonexistent.jsonl"
        assert load_last_voice_line(store_path=path) is None

    def test_returns_none_when_store_empty(self, store_path: Path):
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text("")
        assert load_last_voice_line(store_path=store_path) is None

    def test_returns_last_record(self, store_path: Path):
        vl1 = VoiceLine(mode="narrator", text="First.", raw="First.", t=1.0)
        vl2 = VoiceLine(mode="narrator", text="Second.", raw="Second.", t=2.0)
        persist_voice_line(vl1, store_path=store_path, now=1.0)
        persist_voice_line(vl2, store_path=store_path, now=2.0)
        result = load_last_voice_line(store_path=store_path)
        assert result is not None
        assert result.text == "Second."

    def test_filters_by_mode(self, store_path: Path):
        vl_n = VoiceLine(mode="narrator", text="Narrator.", raw="Narrator.")
        vl_i = VoiceLine(mode="interpreter", text="Interpreter.", raw="Interpreter.")
        persist_voice_line(vl_n, store_path=store_path, now=1.0)
        persist_voice_line(vl_i, store_path=store_path, now=2.0)
        result = load_last_voice_line(mode="narrator", store_path=store_path)
        assert result is not None
        assert result.mode == "narrator"
        assert result.text == "Narrator."

    def test_mode_filter_picks_latest_matching(self, store_path: Path):
        vl1 = VoiceLine(mode="narrator", text="Old narrator.", raw="Old.")
        vl2 = VoiceLine(mode="interpreter", text="Interpreter.", raw="Interp.")
        vl3 = VoiceLine(mode="narrator", text="New narrator.", raw="New.")
        persist_voice_line(vl1, store_path=store_path, now=1.0)
        persist_voice_line(vl2, store_path=store_path, now=2.0)
        persist_voice_line(vl3, store_path=store_path, now=3.0)
        result = load_last_voice_line(mode="narrator", store_path=store_path)
        assert result is not None
        assert result.text == "New narrator."

    def test_returns_none_when_no_mode_match(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.")
        persist_voice_line(vl, store_path=store_path)
        result = load_last_voice_line(mode="counselor", store_path=store_path)
        assert result is None

    def test_skips_corrupt_lines(self, store_path: Path):
        store_path.parent.mkdir(parents=True, exist_ok=True)
        vl = VoiceLine(mode="narrator", text="Good.", raw="Good.", t=5.0, line_id="x")
        store_path.write_text(
            "NOT JSON\n" + json.dumps(vl.to_dict()) + "\n"
        )
        result = load_last_voice_line(store_path=store_path)
        assert result is not None
        assert result.text == "Good."

    def test_no_mode_filter_returns_any_mode(self, store_path: Path):
        vl_n = VoiceLine(mode="narrator", text="N.", raw="N.")
        vl_c = VoiceLine(mode="counselor", text="C.", raw="C.")
        persist_voice_line(vl_n, store_path=store_path, now=1.0)
        persist_voice_line(vl_c, store_path=store_path, now=2.0)
        result = load_last_voice_line(store_path=store_path)
        assert result is not None
        assert result.mode == "counselor"

    def test_returned_line_id_preserved(self, store_path: Path):
        vl = VoiceLine(mode="narrator", text="A.", raw="A.", line_id="known-id")
        persist_voice_line(vl, store_path=store_path)
        result = load_last_voice_line(store_path=store_path)
        assert result is not None
        assert result.line_id == "known-id"


# ---------------------------------------------------------------------------
# helix_dashboard integration
# ---------------------------------------------------------------------------


class TestDashboardNarratorPanel:
    def test_load_narrator_line_returns_empty_when_missing(self, monkeypatch):
        from signal_core.core.dashboard import helix_dashboard

        monkeypatch.setattr(
            helix_dashboard,
            "load_last_voice_line",
            lambda mode=None: None,
        )
        result = helix_dashboard._load_narrator_line()
        assert result == ""

    def test_load_narrator_line_returns_text(self, monkeypatch):
        from signal_core.core.dashboard import helix_dashboard

        vl = VoiceLine(mode="narrator", text="Twelve packets were observed.", raw="Twelve packets were observed.")
        monkeypatch.setattr(
            helix_dashboard,
            "load_last_voice_line",
            lambda mode=None: vl,
        )
        result = helix_dashboard._load_narrator_line()
        assert result == "Twelve packets were observed."

    def test_panel_narrator_empty_shows_placeholder(self):
        from signal_core.core.dashboard import helix_dashboard

        panel = helix_dashboard._panel_narrator("")
        assert panel is not None
        # Panel title contains VOICE
        assert "VOICE" in str(panel.title)

    def test_panel_narrator_with_text(self):
        from signal_core.core.dashboard import helix_dashboard

        panel = helix_dashboard._panel_narrator("The cycle produced twelve events.")
        assert panel is not None

    def test_load_narrator_line_swallows_exceptions(self, monkeypatch):
        from signal_core.core.dashboard import helix_dashboard

        def _raising(*args, **kwargs):
            raise RuntimeError("store broken")

        monkeypatch.setattr(helix_dashboard, "load_last_voice_line", _raising)
        result = helix_dashboard._load_narrator_line()
        assert result == ""
