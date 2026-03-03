"""
Voice line persistence — append-only store for narrator/interpreter/counselor output.

Each voice mode (Narrator, Interpreter, Gate Counselor) can persist its output
here so the helix dashboard can display the most recent line without re-running
the LLM on every refresh.

Store format: append-only JSONL at VOICE_LINES_PATH (one record per line).

Contract:
  - persist_voice_line() always appends; records are never mutated or deleted.
  - load_last_voice_line() returns the most-recent record, optionally filtered by mode.
  - If the store does not exist, load_last_voice_line() returns None (no error).

Typical usage (in a cycle runner, after narrate()):

    from rhythm_os.voice.narrator import narrate
    from rhythm_os.voice.voice_store import persist_voice_line, VoiceLine

    result = narrate(cycle_summary)
    vl = VoiceLine(mode="narrator", text=result.text, raw=result.raw)
    persist_voice_line(vl)

The dashboard then calls load_last_voice_line(mode="narrator") on each refresh.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from rhythm_os.runtime.paths import VOICE_LINES_PATH


# ---------------------------------------------------------------------------
# VoiceLine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceLine:
    """
    A persisted voice output record.

    mode  "narrator" | "interpreter" | "counselor"
    text  The trimmed display text shown on the dashboard.
    raw   Raw LLM output before guard processing.
    t     Unix timestamp (float, UTC). Set automatically by persist_voice_line.
    line_id  UUID. Set automatically by persist_voice_line.
    """

    mode: str
    text: str
    raw: str
    t: float = 0.0
    line_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VoiceLine":
        return cls(
            mode=d["mode"],
            text=d["text"],
            raw=d["raw"],
            t=float(d.get("t", 0.0)),
            line_id=str(d.get("line_id", "")),
        )


# ---------------------------------------------------------------------------
# persist_voice_line
# ---------------------------------------------------------------------------


def persist_voice_line(
    vl: VoiceLine,
    *,
    store_path: Optional[Path] = None,
    now: Optional[float] = None,
) -> VoiceLine:
    """
    Append a voice line to the store.

    Parameters
    ----------
    vl          VoiceLine to persist. t and line_id are set if not already provided.
    store_path  Override path (defaults to VOICE_LINES_PATH).
    now         Override timestamp (defaults to time.time()).

    Returns
    -------
    VoiceLine  The persisted record with t and line_id filled in.
    """
    path = store_path if store_path is not None else VOICE_LINES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    ts = now if now is not None else time.time()
    lid = vl.line_id if vl.line_id else str(uuid.uuid4())

    record = VoiceLine(
        mode=vl.mode,
        text=vl.text,
        raw=vl.raw,
        t=ts,
        line_id=lid,
    )

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict()) + "\n")

    return record


# ---------------------------------------------------------------------------
# load_last_voice_line
# ---------------------------------------------------------------------------


def load_last_voice_line(
    mode: Optional[str] = None,
    *,
    store_path: Optional[Path] = None,
) -> Optional[VoiceLine]:
    """
    Return the most-recent voice line, optionally filtered by mode.

    Parameters
    ----------
    mode        If given, only consider records with this mode ("narrator", etc.).
    store_path  Override path (defaults to VOICE_LINES_PATH).

    Returns
    -------
    VoiceLine or None if the store does not exist or has no matching records.
    """
    path = store_path if store_path is not None else VOICE_LINES_PATH
    if not path.exists():
        return None

    last: Optional[VoiceLine] = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    d = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                vl = VoiceLine.from_dict(d)
                if mode is None or vl.mode == mode:
                    last = vl
    except Exception:
        return None

    return last
