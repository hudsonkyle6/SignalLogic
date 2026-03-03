#!/usr/bin/env python3
"""
Synthetic Cyber Attack Observatory
POSTURE: OBSERVATORY (synthetic data source)

Generates realistic cyber attack telemetry and writes it to the cyber attack
dark field for downstream PSR projection.  No real network scanning is
performed — all data is synthetically generated from parametric models.

Scenarios
---------
  baseline     Normal background traffic.  Low rates, no anomalies.
  port_scan    Systematic port scan from a small IP set.
  ddos         Distributed denial-of-service from a large botnet.
  brute_force  Credential brute-force against auth services.
  apt          Advanced persistent threat — slow, subtle, deliberate.

Usage
-----
  python apps/observatory_tools/emit_cyber_attack_raw.py
  python apps/observatory_tools/emit_cyber_attack_raw.py --scenario ddos --intensity 0.8
  python apps/observatory_tools/emit_cyber_attack_raw.py --scenario apt --intensity 0.4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from signal_core.core.log import configure, get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------

from rhythm_os.runtime.paths import DATA_DIR

CYBER_ATTACK_DIR = DATA_DIR / "dark_field" / "cyber_attack"

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

# Each scenario defines (mean, std) for each metric at intensity=1.0.
# Values are scaled by intensity at generation time.
#
# Metrics:
#   connection_attempt_rate  — new TCP connections per second
#   auth_failure_rate        — authentication failures per second
#   inbound_bps              — inbound bytes per second
#   inbound_pps              — inbound packets per second
#   unique_src_ips           — distinct source IPs in observation window
#   unique_dst_ports         — distinct destination ports targeted
#   packet_drop_rate         — fraction of packets dropped by firewall [0,1]
#   geographic_entropy       — Shannon entropy of source geo-distribution [0,1]

_SCENARIOS: dict[str, dict[str, tuple[float, float]]] = {
    "baseline": {
        "connection_attempt_rate": (8.0, 2.0),
        "auth_failure_rate": (0.2, 0.1),
        "inbound_bps": (800_000.0, 200_000.0),
        "inbound_pps": (600.0, 100.0),
        "unique_src_ips": (120.0, 30.0),
        "unique_dst_ports": (7.0, 2.0),
        "packet_drop_rate": (0.002, 0.001),
        "geographic_entropy": (0.55, 0.05),
    },
    "port_scan": {
        "connection_attempt_rate": (1200.0, 200.0),
        "auth_failure_rate": (12.0, 4.0),
        "inbound_bps": (4_000_000.0, 800_000.0),
        "inbound_pps": (8_000.0, 1_500.0),
        "unique_src_ips": (3.0, 2.0),
        "unique_dst_ports": (2500.0, 500.0),
        "packet_drop_rate": (0.15, 0.04),
        "geographic_entropy": (0.18, 0.05),
    },
    "ddos": {
        "connection_attempt_rate": (45_000.0, 8_000.0),
        "auth_failure_rate": (30.0, 10.0),
        "inbound_bps": (300_000_000.0, 60_000_000.0),
        "inbound_pps": (200_000.0, 40_000.0),
        "unique_src_ips": (18_000.0, 4_000.0),
        "unique_dst_ports": (2.0, 1.0),
        "packet_drop_rate": (0.55, 0.10),
        "geographic_entropy": (0.88, 0.05),
    },
    "brute_force": {
        "connection_attempt_rate": (45.0, 10.0),
        "auth_failure_rate": (280.0, 50.0),
        "inbound_bps": (600_000.0, 150_000.0),
        "inbound_pps": (500.0, 100.0),
        "unique_src_ips": (6.0, 3.0),
        "unique_dst_ports": (2.0, 1.0),
        "packet_drop_rate": (0.05, 0.02),
        "geographic_entropy": (0.22, 0.06),
    },
    "apt": {
        "connection_attempt_rate": (5.0, 1.5),
        "auth_failure_rate": (6.0, 2.0),
        "inbound_bps": (1_200_000.0, 300_000.0),
        "inbound_pps": (900.0, 150.0),
        "unique_src_ips": (12.0, 4.0),
        "unique_dst_ports": (3.0, 1.0),
        "packet_drop_rate": (0.008, 0.003),
        "geographic_entropy": (0.42, 0.08),
    },
}

# Organization (coherence) of each attack type at intensity=1.0.
# Represents how structured/systematic the attack pattern is.
_ORGANIZATION: dict[str, tuple[float, float]] = {
    "baseline":    (0.06, 0.03),
    "port_scan":   (0.82, 0.06),
    "ddos":        (0.74, 0.08),
    "brute_force": (0.88, 0.05),
    "apt":         (0.18, 0.06),
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _gauss_clamp(mean: float, std: float, lo: float = 0.0, hi: float = 1e12) -> float:
    return max(lo, min(hi, random.gauss(mean, std)))


def generate_record(
    scenario: str = "baseline",
    intensity: float = 1.0,
    ts: float | None = None,
) -> dict:
    """
    Generate one synthetic attack telemetry record.

    Parameters
    ----------
    scenario   One of: baseline, port_scan, ddos, brute_force, apt
    intensity  Scale factor [0.0, 1.0] — 0 = no attack, 1 = full scenario
    ts         Unix timestamp (defaults to now)
    """
    if scenario not in _SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from: {list(_SCENARIOS)}")
    intensity = max(0.0, min(1.0, intensity))
    ts = ts or time.time()

    base = _SCENARIOS[scenario]
    org_mean, org_std = _ORGANIZATION[scenario]

    # Scale means by intensity; keep std proportional
    rec: dict = {"t": ts, "scenario": scenario, "intensity": intensity}
    for key, (mean, std) in base.items():
        scaled_mean = mean * intensity
        scaled_std = std * intensity if intensity > 0 else std * 0.1
        lo = 0.0
        hi = 1.0 if key in ("packet_drop_rate", "geographic_entropy") else 1e12
        rec[key] = round(_gauss_clamp(scaled_mean, scaled_std, lo=lo, hi=hi), 4)

    # Ensure integer-valued fields
    rec["unique_src_ips"] = max(1, int(rec["unique_src_ips"]))
    rec["unique_dst_ports"] = max(1, int(rec["unique_dst_ports"]))

    # Organization score (coherence of attack pattern)
    rec["organization"] = round(
        _gauss_clamp(org_mean * (0.3 + 0.7 * intensity), org_std, lo=0.0, hi=1.0), 4
    )

    # Derived anomaly score — weighted combination of attack indicators
    rec["anomaly_score"] = round(
        min(1.0,
            0.25 * min(1.0, rec["connection_attempt_rate"] / 10_000.0)
            + 0.30 * min(1.0, rec["auth_failure_rate"] / 500.0)
            + 0.20 * min(1.0, rec["inbound_bps"] / 1_000_000_000.0)
            + 0.15 * min(1.0, rec["unique_dst_ports"] / 5_000.0)
            + 0.10 * rec["geographic_entropy"]
        ),
        4,
    )

    return rec


def emit(scenario: str = "baseline", intensity: float = 1.0) -> dict:
    """
    Generate one record and append it to today's cyber attack dark field file.
    Returns the record dict.
    """
    rec = generate_record(scenario=scenario, intensity=intensity)

    CYBER_ATTACK_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = CYBER_ATTACK_DIR / f"{today}.jsonl"

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    log.info(
        "cyber_attack scenario=%s intensity=%.2f anomaly=%.3f organization=%.3f",
        scenario,
        intensity,
        rec["anomaly_score"],
        rec["organization"],
    )
    return rec


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Emit synthetic cyber attack telemetry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
scenarios:
  baseline     Normal background traffic (NOISE cycles)
  port_scan    Systematic port scan — LAG pattern (cyber leads system)
  ddos         Distributed denial-of-service — COUPLING (all domains respond)
  brute_force  Credential brute force — LAG pattern
  apt          Advanced persistent threat — subtle LAG, low anomaly score
""",
    )
    ap.add_argument(
        "--scenario",
        choices=list(_SCENARIOS),
        default="baseline",
        help="Attack scenario to simulate (default: baseline)",
    )
    ap.add_argument(
        "--intensity",
        type=float,
        default=1.0,
        metavar="0.0-1.0",
        help="Attack intensity scale factor (default: 1.0)",
    )
    ap.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of records to emit (default: 1)",
    )
    args = ap.parse_args()

    configure()
    for _ in range(args.count):
        rec = emit(scenario=args.scenario, intensity=args.intensity)
        print(
            f"scenario={rec['scenario']}  intensity={rec['intensity']:.2f}"
            f"  anomaly={rec['anomaly_score']:.3f}  org={rec['organization']:.3f}"
        )


if __name__ == "__main__":
    main()
