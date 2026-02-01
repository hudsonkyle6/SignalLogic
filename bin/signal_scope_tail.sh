#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT"

DAY="${1:-$(date +%Y-%m-%d)}"
N="${2:-120}"

FILE="rhythm_os/data/dark_field/${DAY}.jsonl"

if [[ ! -f "$FILE" ]]; then
  echo "missing: $FILE" >&2
  exit 1
fi

# Read last N lines (packets) and render as simple wave-like views.
# NOTE: This script does not write anything. It only reads the file and prints.
python - << PY
import json
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from rhythm_os.scope.signal_scope import render_scope

path = Path("${FILE}")
n = int("${N}")

lines = path.read_text(encoding="utf-8").splitlines()[-n:]

@dataclass(frozen=True)
class View:
    t: float
    coherence: float
    phase_spread: float
    buffer_margin: float
    persistence: int
    drift: Optional[float] = None
    afterglow: Optional[float] = None

# Best-effort projection from packets -> display channels:
# - coherence: if present, else 0
# - phase_spread: use phase_diff as a proxy in radians-scale display (bounded)
# - buffer_margin: if missing, display 1.0 (no proximity)
# - persistence: 1 per packet (scope is presentation-only)
views = []
for ln in lines:
    try:
        p = json.loads(ln)
    except Exception:
        continue
    t = float(p.get("t", 0.0))
    coh = p.get("coherence")
    coh = float(coh) if coh is not None else 0.0

    # phase_diff is not "phase_spread" but it's the only oscillatory scalar in many packets.
    pd = p.get("phase_diff", 0.0)
    try:
        pd = float(pd)
    except Exception:
        pd = 0.0

    # buffer_margin absent -> presentation-only: assume 1.0
    bm = p.get("buffer_margin")
    bm = float(bm) if bm is not None else 1.0

    drift = p.get("drift")
    drift = float(drift) if drift is not None else None

    afterglow = p.get("afterglow")
    afterglow = float(afterglow) if afterglow is not None else None

    views.append(View(
        t=t,
        coherence=coh,
        phase_spread=pd,      # proxy
        buffer_margin=bm,
        persistence=1,
        drift=drift,
        afterglow=afterglow,
    ))

render_scope(views, window=min(len(views), 120))
PY
