from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

OUT_DIR = Path("src/rhythm_os/data/dark_field/natural")


def _append_jsonl(path: Path, rec: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _try_lane_observation(window_days: int) -> Optional[Dict[str, Any]]:
    """
    Attempt to use the local natural lane (may be ignored/untracked but present).
    Returns a dict with keys phase_external/phase_field/phase_diff/coherence if available.
    """
    try:
        # Local lane module (may exist even if not tracked)
        from apps.signal_observatory.lanes.natural import loader  # type: ignore
    except Exception:
        return None

    # We accept any of these adapter shapes without forcing a refactor in the lane:
    # - loader.load(window_days=...) -> dict
    # - loader.load(window_s=...) -> dict
    # - loader.run(...) -> dict
    candidates = []
    for fn_name in ("load", "run", "observe"):
        fn = getattr(loader, fn_name, None)
        if callable(fn):
            candidates.append(fn)

    for fn in candidates:
        try:
            out = fn(window_days=window_days)  # preferred signature
            if isinstance(out, dict):
                return out
        except TypeError:
            pass
        except Exception:
            continue

        try:
            out = fn(window_s=float(window_days) * 86400.0)  # alternate signature
            if isinstance(out, dict):
                return out
        except Exception:
            continue

    return None


def main(*, window_days: int = 7) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    now = float(time.time())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.jsonl"

    observed = _try_lane_observation(window_days=window_days) or {}

    # Normalize expected measurement fields (no decisions; these are observations)
    phase_external = float(observed.get("phase_external", 0.0))
    phase_field = float(observed.get("phase_field", 0.0))
    phase_diff = float(observed.get("phase_diff", 0.0))
    coherence = observed.get("coherence", None)
    if coherence is not None:
        coherence = float(coherence)

    channel = str(observed.get("channel", "helix_projection"))
    field_cycle = str(observed.get("field_cycle", "computed"))

    rec = {
        "t": now,
        "domain": "natural_raw",
        "lane": "natural",
        "channel": channel,
        "field_cycle": field_cycle,
        "window_s": int(window_days) * 86400,
        "data": {
            "phase_external": phase_external,
            "phase_field": phase_field,
            "phase_diff": phase_diff,
            "coherence": coherence,
        },
        "extractor": {
            "source": "signal_observatory.natural",
            "runner": "emit_natural_raw",
            "version": "v1",
        },
    }

    _append_jsonl(out_path, rec)
    print(f"OBSERVATORY: wrote 1 natural raw record -> {out_path}")


if __name__ == "__main__":
    main(window_days=7)
