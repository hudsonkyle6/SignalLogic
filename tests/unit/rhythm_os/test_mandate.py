"""
Tests for rhythm_os.control_plane

Modules covered:
- mandate.py          (Mandate, validate_mandate_dict, is_fresh)
- execution_interlock.py  (may_actuate, InterlockDecision)
- actuation_validate.py   (validate_actuation_payload, ActuationContractError)

Invariants:
- Mandate.from_dict parses all required fields correctly
- validate_mandate_dict raises MandateError for each missing/invalid field
- is_fresh returns True within [issued_at, expires_at], False outside
- OBSERVATORY_ONLY posture always denies actuation regardless of mandate
- may_actuate: None mandate → denied; stale mandate → denied
- validate_actuation_payload raises ActuationContractError for missing keys
- mandate_id is deterministic: same dict → same id
"""

from __future__ import annotations

import time
import pytest

from rhythm_os.control_plane.mandate import (
    Mandate,
    MandateError,
    validate_mandate_dict,
    is_fresh,
)
from rhythm_os.control_plane.execution_interlock import (
    InterlockDecision,
    may_actuate,
)
from rhythm_os.control_plane.actuation_validate import (
    ActuationContractError,
    validate_actuation_payload,
)


NOW = int(time.time())


def _mandate_dict(**overrides) -> dict:
    defaults = {
        "principal": "engineer-1",
        "issued_at": NOW - 60,
        "expires_at": NOW + 3600,
        "scope": "read_only",
        "nonce": "abc123",
        "signature": "human-sig-001",
    }
    defaults.update(overrides)
    return defaults


def _mandate(**overrides) -> Mandate:
    return Mandate.from_dict(_mandate_dict(**overrides))


# ------------------------------------------------------------------
# Mandate construction
# ------------------------------------------------------------------


class TestMandateFromDict:
    def test_returns_mandate(self):
        assert isinstance(_mandate(), Mandate)

    def test_principal_set(self):
        m = _mandate(principal="alice")
        assert m.principal == "alice"

    def test_scope_set(self):
        m = _mandate(scope="model_update")
        assert m.scope == "model_update"

    def test_is_frozen(self):
        m = _mandate()
        with pytest.raises((TypeError, AttributeError)):
            m.principal = "hacker"  # type: ignore[misc]


class TestMandateId:
    def test_returns_64_char_hex(self):
        m = _mandate()
        mid = m.mandate_id()
        assert len(mid) == 64
        assert all(c in "0123456789abcdef" for c in mid)

    def test_deterministic(self):
        m1 = _mandate()
        m2 = _mandate()
        assert m1.mandate_id() == m2.mandate_id()

    def test_different_principals_different_id(self):
        m1 = _mandate(principal="alice")
        m2 = _mandate(principal="bob")
        assert m1.mandate_id() != m2.mandate_id()


# ------------------------------------------------------------------
# validate_mandate_dict
# ------------------------------------------------------------------


class TestValidateMandateDict:
    def test_valid_dict_does_not_raise(self):
        validate_mandate_dict(_mandate_dict())  # no exception

    @pytest.mark.parametrize(
        "key", ["principal", "issued_at", "expires_at", "scope", "nonce", "signature"]
    )
    def test_missing_key_raises(self, key):
        d = _mandate_dict()
        del d[key]
        with pytest.raises(MandateError, match="missing keys"):
            validate_mandate_dict(d)

    def test_empty_principal_raises(self):
        with pytest.raises(MandateError, match="principal"):
            validate_mandate_dict(_mandate_dict(principal="   "))

    def test_empty_scope_raises(self):
        with pytest.raises(MandateError, match="scope"):
            validate_mandate_dict(_mandate_dict(scope=""))

    def test_empty_signature_raises(self):
        with pytest.raises(MandateError, match="signature"):
            validate_mandate_dict(_mandate_dict(signature=""))

    def test_expires_at_equal_issued_at_raises(self):
        t = NOW
        with pytest.raises(MandateError, match="expires_at"):
            validate_mandate_dict(_mandate_dict(issued_at=t, expires_at=t))

    def test_expires_at_before_issued_at_raises(self):
        with pytest.raises(MandateError, match="expires_at"):
            validate_mandate_dict(_mandate_dict(issued_at=NOW + 100, expires_at=NOW))

    def test_issued_at_far_future_raises(self):
        far_future = NOW + 600  # > 5-minute tolerance
        with pytest.raises(MandateError, match="issued_at"):
            validate_mandate_dict(
                _mandate_dict(issued_at=far_future, expires_at=far_future + 3600)
            )


# ------------------------------------------------------------------
# is_fresh
# ------------------------------------------------------------------


class TestIsFresh:
    def test_fresh_mandate_is_fresh(self):
        m = _mandate()
        assert is_fresh(m) is True

    def test_expired_mandate_is_not_fresh(self):
        m = _mandate(issued_at=NOW - 7200, expires_at=NOW - 3600)
        assert is_fresh(m) is False

    def test_future_mandate_is_not_fresh(self):
        m = _mandate(issued_at=NOW + 1000, expires_at=NOW + 2000)
        assert is_fresh(m, now=NOW) is False

    def test_exactly_at_expiry_is_fresh(self):
        m = _mandate(issued_at=NOW - 10, expires_at=NOW)
        assert is_fresh(m, now=NOW) is True

    def test_one_second_past_expiry_is_stale(self):
        m = _mandate(issued_at=NOW - 10, expires_at=NOW - 1)
        assert is_fresh(m, now=NOW) is False


# ------------------------------------------------------------------
# may_actuate — OBSERVATORY_ONLY always denies
# ------------------------------------------------------------------


class TestMayActuate:
    def test_observatory_only_denies_with_valid_mandate(self):
        m = _mandate()
        result = may_actuate(m)
        assert result.allowed is False
        assert "OBSERVATORY_ONLY" in result.reason

    def test_observatory_only_denies_without_mandate(self):
        result = may_actuate(None)
        assert result.allowed is False

    def test_returns_interlock_decision(self):
        result = may_actuate(None)
        assert isinstance(result, InterlockDecision)

    def test_observatory_only_denies_fresh_mandate(self):
        # Even a perfectly valid, fresh mandate cannot override OBSERVATORY_ONLY
        m = _mandate()
        assert is_fresh(m) is True
        result = may_actuate(m)
        assert result.allowed is False

    def test_observatory_only_reason_field_non_empty(self):
        result = may_actuate(None)
        assert result.reason


# ------------------------------------------------------------------
# validate_actuation_payload
# ------------------------------------------------------------------


class TestValidateActuationPayload:
    def _valid(self, **overrides) -> dict:
        d = {
            "t": NOW,
            "action": "adjust_setpoint",
            "scope": "compressor_bank_1",
            "mandate_id": "a" * 64,
            "intent_hash": "b" * 64,
        }
        d.update(overrides)
        return d

    def test_valid_payload_does_not_raise(self):
        validate_actuation_payload(self._valid())  # no exception

    @pytest.mark.parametrize(
        "key", ["t", "action", "scope", "mandate_id", "intent_hash"]
    )
    def test_missing_key_raises(self, key):
        d = self._valid()
        del d[key]
        with pytest.raises(ActuationContractError, match="missing keys"):
            validate_actuation_payload(d)

    def test_empty_mandate_id_raises(self):
        with pytest.raises(ActuationContractError, match="mandate_id"):
            validate_actuation_payload(self._valid(mandate_id="   "))

    def test_whitespace_mandate_id_raises(self):
        with pytest.raises(ActuationContractError):
            validate_actuation_payload(self._valid(mandate_id="\t\n"))
