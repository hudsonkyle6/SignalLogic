#!/usr/bin/env python3
"""
Cyber Attack → Domain projection (PSR)
POSTURE: PSR ONLY — read raw attack data, project to DomainWaves.

Reads the latest synthetic cyber attack raw records and projects them into
DomainWave records with channel="attack_pressure".  Phase is derived from
the attack lifecycle position; coherence reflects how organized the attack is.

Phase mapping
-------------
  phase_external = π × anomaly_score
      0     = no attack (baseline)
      π/2   = moderate attack (port scan, APT)
      π     = severe attack (DDoS at full intensity)

  coherence = organization score of the attack pattern
      near 0 = chaotic / baseline / APT
      near 1 = highly systematic (brute force, port scan)
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.core.field import compute_field
from rhythm_os.core.phasor_merge import wrap_angle
from rhythm_os.runtime.paths import DATA_DIR, DOMAIN_DIR
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)

CYBER_ATTACK_DIR = DATA_DIR / "dark_field" / "cyber_attack"
DOMAIN = "cyber"
CHANNEL = "attack_pressure"
FIELD_CYCLE = "cyber_attack_v1"


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


def _latest_attack_file() -> Path:
    files = sorted(CYBER_ATTACK_DIR.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No cyber attack data at {CYBER_ATTACK_DIR}")
    return files[-1]


def _read_attack_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def project_cyber_attack_domain() -> List[DomainWave]:
    """
    Project synthetic cyber attack records into DomainWaves.

    Each record → one DomainWave with:
        phase_external = π × anomaly_score   (attack severity as phase)
        coherence      = organization score  (how structured the attack is)
        phase_field    = sovereign reference phase at record timestamp
        phase_diff     = phase_external − phase_field (wrapped)
    """
    path = _latest_attack_file()
    records = _read_attack_records(path)

    waves: List[DomainWave] = []

    for rec in records:
        ts = float(rec["t"])

        # Sovereign reference phase at observation time
        field = compute_field(ts)
        phi_field = field.reference_phase

        # Attack phase: maps anomaly_score [0,1] → [0, π]
        anomaly_score = float(rec.get("anomaly_score", 0.0))
        phi_external = math.pi * anomaly_score

        # Phase difference (attack vs sovereign field)
        phase_diff = wrap_angle(phi_external - phi_field)

        # Coherence = organization of the attack
        coherence = float(rec.get("organization", 0.0))

        dw = DomainWave(
            t=ts,
            domain=DOMAIN,
            channel=CHANNEL,
            field_cycle=FIELD_CYCLE,
            phase_external=phi_external,
            phase_field=phi_field,
            phase_diff=phase_diff,
            coherence=coherence,
            extractor={
                "source": "emit_cyber_attack_domain",
                "scenario": str(rec.get("scenario", "unknown")),
                "intensity": str(rec.get("intensity", 0.0)),
                "anomaly_score": str(round(anomaly_score, 4)),
                "version": "v1_cyber_attack",
            },
        )
        waves.append(dw)

    return waves


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------


def main() -> None:
    waves = project_cyber_attack_domain()
    if not waves:
        log.info("CYBER ATTACK PSR: no records to project")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = DOMAIN_DIR / f"{today}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    for dw in waves:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "t": dw.t,
                        "domain": dw.domain,
                        "channel": dw.channel,
                        "field_cycle": dw.field_cycle,
                        "phase_external": dw.phase_external,
                        "phase_field": dw.phase_field,
                        "phase_diff": dw.phase_diff,
                        "coherence": dw.coherence,
                        "extractor": dw.extractor,
                    },
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            )
        written += 1

    last = waves[-1]
    log.info(
        "CYBER ATTACK DOMAIN: wrote %d waves  last: scenario=%s anomaly=%.3f coherence=%.3f",
        written,
        last.extractor.get("scenario", "?"),
        float(last.extractor.get("anomaly_score", 0)),
        last.coherence or 0.0,
    )


if __name__ == "__main__":
    configure()
    main()
