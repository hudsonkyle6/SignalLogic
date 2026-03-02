# rhythm_os/core/wave/wave.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Dict, Mapping, Optional, Any
import json
import hashlib


# ------------------------------------------------------------
# INTERNAL: canonicalization + deterministic hash
# ------------------------------------------------------------


def _fmt_float(x: float) -> str:
    """
    Canonical float formatting for hashing.
    Keeps stored fields as floats (for readability), but hashes a stable string form.
    """
    return format(float(x), ".10g")


def _canonical_couplings(c: Mapping[str, float]) -> Dict[str, str]:
    """
    Canonical couplings for hashing/serialization:
    - keys sorted deterministically
    - values formatted deterministically
    """
    if not c:
        return {}
    return {k: _fmt_float(c[k]) for k in sorted(c.keys())}


def _canonical_wave_payload(
    *,
    signal_type: str,
    phase: float,
    frequency: float,
    amplitude: float,
    afterglow_decay: float,
    timestamp: str,
    couplings: Mapping[str, float],
    text_content: str,
) -> Dict[str, Any]:
    """
    Canonical payload used for integrity hashing.
    NOTE: uses stringified floats to avoid FP nondeterminism across platforms.
    """
    return {
        "signal_type": signal_type,
        "phase": _fmt_float(phase),
        "frequency": _fmt_float(frequency),
        "amplitude": _fmt_float(amplitude),
        "afterglow_decay": _fmt_float(afterglow_decay),
        "timestamp": timestamp,
        "couplings": _canonical_couplings(couplings),
        "text_content": text_content,
    }


def _hash_wave_payload(payload: Dict[str, Any]) -> str:
    """
    Deterministic integrity hash over canonical payload.
    """
    blob = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ------------------------------------------------------------
# WAVE — OS-LEVEL PRIMITIVE
# ------------------------------------------------------------


@dataclass(frozen=True)
class Wave:
    """
    Wave is a sealed observational record.

    It represents:
    - one signal
    - one domain
    - one moment in time

    It does NOT predict, decide, or infer authority.
    """

    # identity
    signal_type: str

    # oscillatory descriptors
    phase: float
    frequency: float
    amplitude: float
    afterglow_decay: float

    # record
    timestamp: str
    couplings: Mapping[str, float]
    text_content: str

    # integrity
    integrity_hash: str

    def __post_init__(self) -> None:
        # Enforce immutability of couplings
        if isinstance(self.couplings, MappingProxyType):
            return
        object.__setattr__(
            self, "couplings", MappingProxyType(dict(self.couplings or {}))
        )

    # --------------------------------------------------------
    # FACTORY
    # --------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        text: str,
        signal_type: str,
        phase: float = 0.0,
        frequency: float = 1.0,
        amplitude: float = 1.0,
        afterglow_decay: float = 0.5,
        couplings: Optional[Dict[str, float]] = None,
        timestamp: Optional[str] = None,
    ) -> Wave:
        """
        Create a new sealed Wave.
        Hash is computed ONCE from stored fields.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        base = {
            "signal_type": signal_type,
            "phase": float(phase),
            "frequency": float(frequency),
            "amplitude": float(amplitude),
            "afterglow_decay": float(afterglow_decay),
            "timestamp": ts,
            "couplings": dict(couplings or {}),
            "text_content": text,
        }

        payload = _canonical_wave_payload(
            signal_type=base["signal_type"],
            phase=base["phase"],
            frequency=base["frequency"],
            amplitude=base["amplitude"],
            afterglow_decay=base["afterglow_decay"],
            timestamp=base["timestamp"],
            couplings=base["couplings"],
            text_content=base["text_content"],
        )

        h = _hash_wave_payload(payload)

        return cls(**base, integrity_hash=h)

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def verify_integrity(self) -> bool:
        """
        Recompute hash from stored fields and compare.
        Fully deterministic.
        """
        payload = _canonical_wave_payload(
            signal_type=self.signal_type,
            phase=self.phase,
            frequency=self.frequency,
            amplitude=self.amplitude,
            afterglow_decay=self.afterglow_decay,
            timestamp=self.timestamp,
            couplings=self.couplings,
            text_content=self.text_content,
        )
        return _hash_wave_payload(payload) == self.integrity_hash

    # --------------------------------------------------------
    # SERIALIZATION (JSONL-SAFE)
    # --------------------------------------------------------

    def to_json(self) -> str:
        """
        Compact JSON serialization for JSONL penstock.
        One Wave per line.
        """
        return json.dumps(
            {
                "signal_type": self.signal_type,
                "phase": self.phase,
                "frequency": self.frequency,
                "amplitude": self.amplitude,
                "afterglow_decay": self.afterglow_decay,
                "timestamp": self.timestamp,
                "couplings": dict(self.couplings),
                "text_content": self.text_content,
                "integrity_hash": self.integrity_hash,
            },
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> Wave:
        """
        Rehydrate a sealed Wave.
        """
        data = json.loads(json_str)

        couplings = data.get("couplings") or {}
        data["couplings"] = dict(couplings)

        return cls(**data)
