from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json
import time
import hashlib


@dataclass(frozen=True)
class Mandate:
    """
    Human mandate = permission key, not an instruction.
    This object is intentionally minimal.

    Required:
      - principal: who authorizes (human identifier string)
      - issued_at: unix seconds when issued
      - expires_at: unix seconds when mandate expires
      - scope: a short scope string describing what is allowed (not how)
      - nonce: random-ish string (human or tool generated)
      - signature: human-provided signature string (can be wet-sign + transcription)

    Notes:
      - No conditionals, no logic, no automation flags.
      - Validation is purely structural + time freshness.
      - Signature verification (cryptographic) is intentionally NOT implemented here.
    """
    principal: str
    issued_at: int
    expires_at: int
    scope: str
    nonce: str
    signature: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Mandate":
        return Mandate(
            principal=str(d["principal"]),
            issued_at=int(d["issued_at"]),
            expires_at=int(d["expires_at"]),
            scope=str(d["scope"]),
            nonce=str(d["nonce"]),
            signature=str(d["signature"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principal": self.principal,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "nonce": self.nonce,
            "signature": self.signature,
        }

    def mandate_id(self) -> str:
        """
        Deterministic ID for audit referencing. Not a security feature.
        """
        payload = json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class MandateError(Exception):
    pass


def validate_mandate_dict(d: Dict[str, Any]) -> None:
    required = ["principal", "issued_at", "expires_at", "scope", "nonce", "signature"]
    missing = [k for k in required if k not in d]
    if missing:
        raise MandateError(f"missing keys: {missing}")

    # Type-ish checks
    if not str(d["principal"]).strip():
        raise MandateError("principal empty")
    if not str(d["scope"]).strip():
        raise MandateError("scope empty")
    if not str(d["signature"]).strip():
        raise MandateError("signature empty")

    issued_at = int(d["issued_at"])
    expires_at = int(d["expires_at"])
    if expires_at <= issued_at:
        raise MandateError("expires_at must be > issued_at")

    # Future skew tolerance: allow small clock skew (5 minutes)
    now = int(time.time())
    if issued_at > now + 300:
        raise MandateError("issued_at too far in the future")

def is_fresh(m: Mandate, now: Optional[int] = None) -> bool:
    """
    Freshness = now within [issued_at, expires_at].
    """
    t = int(time.time()) if now is None else int(now)
    return (m.issued_at <= t) and (t <= m.expires_at)
