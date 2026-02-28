"""
Tests for rhythm_os.runtime.can_packet_validator

Invariants:
- is_pre_contract: packets before 2026-02-02 are pre-contract
- is_pre_contract: packets on or after 2026-02-02 are post-contract
- is_pre_contract: unreadable timestamp returns True (treated as fossil)
- validate_packet: pre-contract packets pass silently (no issues)
- validate_packet: post-contract packets missing top-level fields → issue reported
- validate_packet: post-contract packets with non-dict extractor → issue reported
- validate_packet: post-contract packets with incomplete extractor keys → issue reported
- validate_packet: fully valid post-contract packet → no issues
"""
from __future__ import annotations

import datetime as dt
import pytest

from rhythm_os.runtime.can_packet_validator import (
    is_pre_contract,
    validate_packet,
    CONTRACT_V1_EFFECTIVE,
)

# A timestamp clearly before the contract date (2026-02-02)
PRE_CONTRACT_TS = dt.datetime(2025, 1, 1).timestamp()
# A timestamp clearly after the contract date
POST_CONTRACT_TS = dt.datetime(2026, 6, 1).timestamp()


def _valid_post_contract_packet(**overrides) -> dict:
    base = {
        "t": POST_CONTRACT_TS,
        "domain": "system",
        "channel": "net_pressure",
        "extractor": {
            "source": "unit_test",
            "method": "direct",
            "version": "1.0",
        },
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# is_pre_contract
# ------------------------------------------------------------------

class TestIsPreContract:
    def test_old_float_timestamp_is_pre_contract(self):
        assert is_pre_contract({"t": PRE_CONTRACT_TS}) is True

    def test_new_float_timestamp_is_post_contract(self):
        assert is_pre_contract({"t": POST_CONTRACT_TS}) is False

    def test_isoformat_pre_contract(self):
        assert is_pre_contract({"t": "2025-06-01T00:00:00"}) is True

    def test_isoformat_post_contract(self):
        assert is_pre_contract({"t": "2026-06-01T00:00:00"}) is False

    def test_missing_t_is_pre_contract(self):
        # get() returns None → exception → treated as fossil
        assert is_pre_contract({}) is True

    def test_invalid_t_is_pre_contract(self):
        assert is_pre_contract({"t": "not-a-date"}) is True

    def test_none_t_is_pre_contract(self):
        assert is_pre_contract({"t": None}) is True

    def test_boundary_exactly_on_contract_date_is_post(self):
        # Exactly at CONTRACT_V1_EFFECTIVE → not pre-contract
        ts = CONTRACT_V1_EFFECTIVE.timestamp()
        # fromtimestamp of that ts == CONTRACT_V1_EFFECTIVE, which is NOT < effective
        result = is_pre_contract({"t": ts})
        assert result is False


# ------------------------------------------------------------------
# validate_packet
# ------------------------------------------------------------------

class TestValidatePacket:
    def test_pre_contract_packet_passes_silently(self):
        packet = {"t": PRE_CONTRACT_TS}  # missing everything else
        assert validate_packet(packet) == []

    def test_valid_post_contract_packet_no_issues(self):
        packet = _valid_post_contract_packet()
        assert validate_packet(packet) == []

    def test_missing_required_top_level_fields(self):
        # Remove 'domain' from a post-contract packet
        packet = _valid_post_contract_packet()
        del packet["domain"]
        issues = validate_packet(packet)
        assert any("missing_top_level" in i for i in issues)

    def test_missing_t_treated_as_fossil(self):
        # When 't' is absent, is_pre_contract() catches the exception and
        # returns True → packet is treated as a fossil and passes silently.
        packet = _valid_post_contract_packet()
        del packet["t"]
        issues = validate_packet(packet)
        assert issues == []

    def test_non_dict_extractor_reported(self):
        packet = _valid_post_contract_packet(extractor="string-not-dict")
        issues = validate_packet(packet)
        assert any("missing_or_invalid_extractor" in i for i in issues)

    def test_none_extractor_reported(self):
        packet = _valid_post_contract_packet(extractor=None)
        issues = validate_packet(packet)
        assert any("missing_or_invalid_extractor" in i for i in issues)

    def test_extractor_missing_source_reported(self):
        packet = _valid_post_contract_packet(extractor={"method": "x", "version": "1"})
        issues = validate_packet(packet)
        assert any("missing_extractor" in i for i in issues)

    def test_extractor_missing_method_reported(self):
        packet = _valid_post_contract_packet(extractor={"source": "x", "version": "1"})
        issues = validate_packet(packet)
        assert any("missing_extractor" in i for i in issues)

    def test_extractor_missing_version_reported(self):
        packet = _valid_post_contract_packet(extractor={"source": "x", "method": "direct"})
        issues = validate_packet(packet)
        assert any("missing_extractor" in i for i in issues)

    def test_empty_extractor_reports_all_missing_keys(self):
        packet = _valid_post_contract_packet(extractor={})
        issues = validate_packet(packet)
        assert any("missing_extractor" in i for i in issues)

    def test_returns_list(self):
        issues = validate_packet(_valid_post_contract_packet())
        assert isinstance(issues, list)

    def test_optional_fields_not_required(self):
        # Optional fields absent should not cause issues
        packet = _valid_post_contract_packet()
        # field_cycle, phase_external, etc. are optional — omitting is fine
        assert "field_cycle" not in packet
        assert validate_packet(packet) == []
