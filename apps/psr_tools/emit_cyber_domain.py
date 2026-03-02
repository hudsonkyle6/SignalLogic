# apps/psr_tools/emit_cyber_domain.py

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rhythm_os.psr.domain_wave import DomainWave
from rhythm_os.core.field import compute_field
from rhythm_os.core.phasor_merge import project_samples_to_clocks, wrap_angle
from rhythm_os.core.domain_clocks.cyber import CYBER_CYCLES


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

from rhythm_os.runtime.paths import DOMAIN_DIR, METERS_DIR

DOMAIN = "cyber"
CHANNEL = "cadence_pressure"
FIELD_CYCLE = "cyber_clock_stack_v1"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _meters_path_latest() -> Path:
    files = list(METERS_DIR.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError("No meter files found")
    return max(files, key=lambda p: p.stat().st_mtime)


def _domain_path_today() -> Path:
    return DOMAIN_DIR / f"{_today_str()}.jsonl"


def _read_meter_packets(path: Path) -> List[Dict[str, Any]]:
    packets: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                packets.append(json.loads(line))
    return packets


def _extract_net_samples(pkts: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """
    Returns (t, amplitude) samples.
    For cyber cadence v1 we use out_rate_bps as amplitude (non-negative scalar).
    """
    out: List[Tuple[float, float]] = []
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


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    meters_path = _meters_path_latest()
    pkts = _read_meter_packets(meters_path)

    samples = _extract_net_samples(pkts)
    if len(samples) < 3:
        raise RuntimeError("Not enough net samples for cyber projection")

    # Reference time: latest sample timestamp
    ts = samples[-1][0]

    # Base sovereign field reference phase
    base = compute_field(ts)
    phi_base = base.reference_phase

    # Cyber stack projection (multi-clock)
    proj = project_samples_to_clocks(samples, CYBER_CYCLES)

    # Cyber group phasor / phase / coherence
    phi_cyber = proj.phase
    r_cyber = proj.coherence

    # Phase difference cyber vs base
    phase_diff = wrap_angle(phi_cyber - phi_base)

    # Per-clock coherence detail (kept as trace, not authority)
    per_clock_r = {name: cp.coherence for name, cp in proj.clocks.items()}

    dw = DomainWave(
        t=ts,
        domain=DOMAIN,
        channel=CHANNEL,
        field_cycle=FIELD_CYCLE,
        # We use "external" to mean observed-domain phase posture (cyber group)
        phase_external=phi_cyber,
        # We use "field" to mean sovereign reference (base composite)
        phase_field=phi_base,
        phase_diff=phase_diff,
        # Domain coherence (cyber group coherence)
        coherence=r_cyber,
        extractor={
            "source": "emit_cyber_domain",
            "projection": "multi_clock_phasor_stack",
            "cycles": {k: float(v) for k, v in CYBER_CYCLES.items()},
            "per_clock_coherence": per_clock_r,
            "samples": len(samples),
            "version": "v1_cyber_clock_stack",
        },
    )

    out_path = _domain_path_today()
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

    print(f"CYBER DOMAIN EMITTED → phase_diff={phase_diff:.3f} coherence={r_cyber:.3f}")


if __name__ == "__main__":
    main()
