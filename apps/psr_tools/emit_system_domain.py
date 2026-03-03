# apps/psr_tools/emit_system_domain.py

from __future__ import annotations

import json
import math
import cmath
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rhythm_os.psr.domain_wave import DomainWave


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

T_DIURNAL = 86400.0
OMEGA = 2.0 * math.pi / T_DIURNAL


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

from rhythm_os.runtime.paths import DOMAIN_DIR, METERS_DIR
from signal_core.core.log import configure, get_logger

log = get_logger(__name__)

DOMAIN = "system"
FIELD_CYCLE = "diurnal_projection"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _meters_path_today() -> Path:
    today = _today_str()
    path = METERS_DIR / f"{today}.jsonl"

    if not path.exists():
        raise FileNotFoundError(f"No sovereign meter file for today: {path}")

    log.debug("SYSTEM DOMAIN reading sovereign meters file: %s", path)
    log.debug("SYSTEM DOMAIN mtime: %s", path.stat().st_mtime)

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


def _wrap_angle(theta: float) -> float:
    while theta <= -math.pi:
        theta += 2 * math.pi
    while theta > math.pi:
        theta -= 2 * math.pi
    return theta


# ---------------------------------------------------------------------
# Sample extractors
# ---------------------------------------------------------------------


def _extract_net_samples(pkts: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    out = []
    for p in pkts:
        if str(p.get("lane")) != "net":
            continue
        data = p.get("data") or {}
        try:
            t = float(p["t"])
            out.append((t, float(data.get("out_rate_bps", 0.0))))
        except Exception:
            continue
    return out


def _extract_cpu_util_samples(pkts: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    out = []
    for p in pkts:
        if str(p.get("lane")) != "cpu" or str(p.get("channel")) != "cpu:util":
            continue
        data = p.get("data") or {}
        try:
            t = float(p["t"])
            out.append((t, float(data.get("cpu_percent_mean", 0.0))))
        except Exception:
            continue
    return out


def _extract_proc_samples(pkts: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """Aggregate cpu_rate_core_equiv across all proc channels at each timestamp."""
    by_t: Dict[float, float] = {}
    for p in pkts:
        if str(p.get("lane")) != "proc":
            continue
        data = p.get("data") or {}
        try:
            t = float(p["t"])
            val = float(data.get("cpu_rate_core_equiv", 0.0))
            by_t[t] = by_t.get(t, 0.0) + val
        except Exception:
            continue
    return sorted(by_t.items())


# ---------------------------------------------------------------------
# Phasor projection
# ---------------------------------------------------------------------


def _project(
    samples: List[Tuple[float, float]],
    channel: str,
    extractor_source: str,
    extra_extractor: Optional[Dict[str, Any]] = None,
) -> Optional[DomainWave]:
    if len(samples) < 3:
        return None

    Z = 0j
    mag_sum = 0.0

    for t, val in samples:
        phase = OMEGA * t
        Z += val * cmath.exp(1j * phase)
        mag_sum += abs(val)

    if mag_sum == 0:
        coherence = 0.0
        phase_external = 0.0
    else:
        coherence = abs(Z) / mag_sum
        phase_external = cmath.phase(Z)

    ts = samples[-1][0]
    phase_field = (OMEGA * ts) % (2 * math.pi)
    phase_diff = _wrap_angle(phase_external - phase_field)

    extractor: Dict[str, Any] = {
        "source": extractor_source,
        "projection": "diurnal",
        "samples": len(samples),
        "version": "v1",
    }
    if extra_extractor:
        extractor.update(extra_extractor)

    return DomainWave(
        t=ts,
        domain=DOMAIN,
        channel=channel,
        field_cycle=FIELD_CYCLE,
        phase_external=phase_external,
        phase_field=phase_field,
        phase_diff=phase_diff,
        coherence=coherence,
        extractor=extractor,
    )


# ---------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------


def _emit_wave(dw: DomainWave, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
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


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    meters_path = _meters_path_today()
    pkts = _read_meter_packets(meters_path)
    out_path = _domain_path_today()

    channels = [
        ("net_pressure", _extract_net_samples(pkts), "emit_system_domain.net"),
        ("cpu_pressure", _extract_cpu_util_samples(pkts), "emit_system_domain.cpu"),
        ("proc_pressure", _extract_proc_samples(pkts), "emit_system_domain.proc"),
    ]

    emitted = 0
    for channel, samples, src in channels:
        log.debug("SYSTEM DOMAIN [%s] sample count: %d", channel, len(samples))
        dw = _project(samples, channel=channel, extractor_source=src)
        if dw is None:
            log.warning("SYSTEM DOMAIN [%s] skipped (insufficient samples)", channel)
            continue
        _emit_wave(dw, out_path)
        log.info(
            "SYSTEM DOMAIN [%s] phase_diff=%.3f coherence=%.3f",
            channel,
            dw.phase_diff,
            dw.coherence,
        )
        emitted += 1

    log.info("SYSTEM DOMAIN EMITTED: %d channels", emitted)


if __name__ == "__main__":
    configure()
    main()
