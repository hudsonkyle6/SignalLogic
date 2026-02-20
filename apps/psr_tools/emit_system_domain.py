# apps/psr_tools/emit_system_domain.py

from __future__ import annotations

import json
import math
import cmath
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rhythm_os.psr.domain_wave import DomainWave


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

T_DIURNAL = 86400.0
OMEGA = 2.0 * math.pi / T_DIURNAL


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

METERS_DIR = Path("src/rhythm_os/data/dark_field/meters")
DOMAIN_DIR = Path("src/rhythm_os/data/dark_field/domain")

DOMAIN = "system"
FIELD_CYCLE = "diurnal_projection"
CHANNEL = "net_pressure"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _meters_path_today() -> Path:
    today = _today_str()
    path = METERS_DIR / f"{today}.jsonl"

    if not path.exists():
        raise FileNotFoundError(
            f"No sovereign meter file for today: {path}"
        )

    print("SYSTEM DOMAIN reading sovereign meters file:", path)
    print("SYSTEM DOMAIN mtime:", path.stat().st_mtime)

    return path


def _domain_path_today() -> Path:
    return DOMAIN_DIR / f"{_today_str()}.jsonl"


def _read_meter_packets(path: Path) -> List[Dict[str, Any]]:
    packets = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                packets.append(json.loads(line))
    return packets


def _extract_net_samples(
    pkts: List[Dict[str, Any]]
) -> List[Tuple[float, float]]:
    out = []
    for p in pkts:
        if str(p.get("lane")) != "net":
            continue
        data = p.get("data") or {}
        try:
            t = float(p["t"])
            out_bps = float(data.get("out_rate_bps", 0.0))
            out.append((t, out_bps))
        except Exception:
            continue
    return out


def _wrap_angle(theta: float) -> float:
    while theta <= -math.pi:
        theta += 2 * math.pi
    while theta > math.pi:
        theta -= 2 * math.pi
    return theta


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    meters_path = _meters_path_today()
    pkts = _read_meter_packets(meters_path)

    net = _extract_net_samples(pkts)

    print("SYSTEM DOMAIN net sample count:", len(net))

    if len(net) < 3:
        raise RuntimeError("Not enough net samples")

    # -------------------------------------------------------------
    # External phase projection
    # -------------------------------------------------------------

    Z = 0j
    mag_sum = 0.0

    for t, out_bps in net:
        phase = OMEGA * t
        Z += out_bps * cmath.exp(1j * phase)
        mag_sum += abs(out_bps)

    if mag_sum == 0:
        coherence = 0.0
        phase_external = 0.0
    else:
        coherence = abs(Z) / mag_sum
        phase_external = cmath.phase(Z)

    # -------------------------------------------------------------
    # Field phase at latest timestamp
    # -------------------------------------------------------------

    ts = net[-1][0]
    phase_field = (OMEGA * ts) % (2 * math.pi)
    phase_diff = _wrap_angle(phase_external - phase_field)

    # -------------------------------------------------------------
    # Emit DomainWave
    # -------------------------------------------------------------

    dw = DomainWave(
        t=ts,
        domain=DOMAIN,
        channel=CHANNEL,
        field_cycle=FIELD_CYCLE,
        phase_external=phase_external,
        phase_field=phase_field,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor={
            "source": "emit_system_domain",
            "projection": "diurnal",
            "samples": len(net),
            "version": "v4_sovereign_only",
        },
    )

    out_path = _domain_path_today()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "t": dw.t,
            "domain": dw.domain,
            "channel": dw.channel,
            "field_cycle": dw.field_cycle,
            "phase_external": dw.phase_external,
            "phase_field": dw.phase_field,
            "phase_diff": dw.phase_diff,
            "coherence": dw.coherence,
            "extractor": dw.extractor,
        }, separators=(",", ":"), ensure_ascii=False) + "\n")

    print(
        f"SYSTEM DOMAIN EMITTED → "
        f"phase_diff={phase_diff:.3f} "
        f"coherence={coherence:.3f}"
    )


if __name__ == "__main__":
    main()
