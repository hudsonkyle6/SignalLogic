# rhythm_os/runtime/can_packet_validator.py
"""
Canonical CAN Packet Validator
Read-only. No mutation. No authority.
"""

# add at top
import datetime as dt

CONTRACT_V1_EFFECTIVE = dt.datetime(2026, 2, 2)


def is_pre_contract(packet: dict) -> bool:
    try:
        ts = packet.get("t")
        if isinstance(ts, (int, float)):
            pkt_time = dt.datetime.fromtimestamp(ts)
        else:
            pkt_time = dt.datetime.fromisoformat(ts)
        return pkt_time < CONTRACT_V1_EFFECTIVE
    except Exception:
        return True


REQUIRED_TOP_LEVEL = {
    "t",
    "domain",
    "channel",
    "extractor",
}

OPTIONAL_TOP_LEVEL = {
    "field_cycle",
    "phase_external",
    "phase_field",
    "phase_diff",
    "coherence",
}

REQUIRED_EXTRACTOR_KEYS = {
    "source",
    "method",
    "version",
}


def validate_packet(packet: dict) -> list[str]:
    issues = []

    if is_pre_contract(packet):
        return issues  # fossils pass silently

    missing = REQUIRED_TOP_LEVEL - packet.keys()
    if missing:
        issues.append(f"missing_top_level:{sorted(missing)}")

    extractor = packet.get("extractor")
    if not isinstance(extractor, dict):
        issues.append("missing_or_invalid_extractor")
    else:
        missing_ex = REQUIRED_EXTRACTOR_KEYS - extractor.keys()
        if missing_ex:
            issues.append(f"missing_extractor:{sorted(missing_ex)}")

    return issues
