"""Shared pytest configuration and fixtures for SignalLogic tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Make src/ and apps/ importable without installation
ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "src", ROOT / "apps"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
