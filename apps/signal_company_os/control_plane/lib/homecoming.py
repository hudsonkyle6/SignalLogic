from __future__ import annotations

import json
import time
from pathlib import Path

from .policy import Policy
from signal_core.core.log import get_logger

log = get_logger(__name__)


def run_homecoming(policy: Policy) -> int:
    """
    v0 homecoming is conservative: it writes a timestamped entry and does NOT delete anything.
    """
    entry = {
        "event": "homecoming",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "v0 homecoming: no deletes; indicates daily close of gate + reset of intent.",
    }
    p = Path("apps/signal_company_os/control_plane/audits/homecoming.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    log.info("WROTE: %s", p)
    return 0
