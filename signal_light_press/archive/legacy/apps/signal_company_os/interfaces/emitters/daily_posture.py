from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def emit_daily_posture(artifacts: Dict[str, Any], *, export_dir: Path) -> None:
    """
    Emit daily posture artifacts to disk.

    Rules:
    - Write-only
    - No reads
    - No mutation of artifacts
    """
    export_dir.mkdir(parents=True, exist_ok=True)

    path = export_dir / "daily_posture.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(artifacts, f, indent=2)
