"""
Entry point shim for the ``signallogic-run`` CLI command.

Adds the repo root to sys.path so that ``apps.run_cycle_once`` is importable
when the package is installed in editable mode (``pip install -e .``).
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from apps.run_cycle_once import main as _main

    _main()
