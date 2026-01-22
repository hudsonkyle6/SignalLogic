# rhythm_os/core/wave/codex.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .wave import Wave


class Codex:
    def __init__(self, root: Path):
        self.root = root
        self.codex_dir = root / "codex"
        self.codex_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        name: str,
        *,
        signal_type: str,
        text: str,
        phase: float = 0.0,
        frequency: float = 1.0,
        amplitude: float = 1.0,
        afterglow_decay: float = 0.5,
        couplings: Optional[dict[str, float]] = None,
        timestamp: Optional[str] = None,
    ) -> Wave:
        """
        Create and store a new codex entry as a Wave.
        Returns the Wave object.

        Codex is downstream: it does not "fix", "normalize", or recompute integrity.
        """
        wave = Wave.create(
            text=text,
            signal_type=signal_type,
            phase=phase,
            frequency=frequency,
            amplitude=amplitude,
            afterglow_decay=afterglow_decay,
            couplings=couplings or {},
            timestamp=timestamp,
        )

        wave_path = self.codex_dir / f"{name}.osc.json"
        wave_path.write_text(wave.to_json(), encoding="utf-8")
        return wave

    def load(self, name: str, *, require_valid: bool = True) -> Wave:
        """
        Load a codex entry from canonical JSON.

        If require_valid=True, integrity must pass or we raise.
        """
        wave_path = self.codex_dir / f"{name}.osc.json"
        if not wave_path.exists():
            raise FileNotFoundError(f"Codex entry not found: {wave_path}")

        wave = Wave.from_json(wave_path.read_text(encoding="utf-8"))
        if require_valid and not wave.verify_integrity():
            raise ValueError(f"Integrity check failed for codex entry: {wave_path}")
        return wave

    def reimport_from_text(
        self,
        txt_path: Path,
        new_name: str,
        *,
        signal_type: str,
        couplings: Optional[dict[str, float]] = None,
    ) -> Wave:
        """
        Reimport plain text as a NEW wave (new timestamp, new hash).
        This is lawful only as a new observation record.

        NOTE: This does NOT claim identity with any prior wave.
        """
        text = txt_path.read_text(encoding="utf-8").strip()

        new_wave = Wave.create(
            text=text,
            signal_type=signal_type,
            phase=0.0,
            frequency=1.0,
            amplitude=1.0,
            afterglow_decay=0.5,
            couplings=couplings or {},
        )

        new_path = self.codex_dir / f"{new_name}_reimported.osc.json"
        new_path.write_text(new_wave.to_json(), encoding="utf-8")
        return new_wave
