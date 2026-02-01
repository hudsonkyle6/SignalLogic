from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

@dataclass
class GateEntry:
    purpose: str
    scope: str
    signed: str
    time: str

def append_gate(ledger_path: Path, purpose: str, scope: str, signature: str) -> GateEntry:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = {"purpose": purpose, "scope": scope, "signed": signature, "time": ts}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return GateEntry(**entry)
