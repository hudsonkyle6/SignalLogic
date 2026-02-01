from __future__ import annotations
from pathlib import Path
from typing import Optional
from .codex import Codex
from .wave import Wave

class Exporter:
    def __init__(self, root: Path):
        self.root = root
        self.export_dir = root / "codex_export"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_codex(self, name: str) -> Path:
        """
        Export a codex entry's text_content to a readable .txt mirror.
        Returns the path to the exported file.
        """
        codex = Codex(self.root)
        wave = codex.load(name)
        text = wave.text_content.strip()

        export_path = self.export_dir / f"{name}.txt"
        export_path.write_text(text, encoding="utf-8")

        return export_path

    def export_wave_text(self, wave: Wave, name_prefix: str = "direct_export") -> Path:
        """
        Direct export from Wave object (for testing or manual use).
        """
        text = wave.text_content.strip()
        timestamp_safe = wave.timestamp.replace(":", "-").replace("T", "_").split(".")[0]
        name = f"{name_prefix}_{timestamp_safe}"
        export_path = self.export_dir / f"{name}.txt"
        export_path.write_text(text, encoding="utf-8")
        return export_path
