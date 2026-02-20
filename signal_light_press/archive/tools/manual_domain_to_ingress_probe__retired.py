from __future__ import annotations

import json
import uuid
from pathlib import Path

from rhythm_os.psr.read_domain_waves import read_today
from signal_core.core.hydro_types import HydroPacket

INGRESS_PATH = Path("src/rhythm_os/data/dark_field/hydro/ingress.jsonl")


def main() -> None:
    waves = read_today()

    if not waves:
        raise RuntimeError("No DomainWaves available for probe")

    # Take the most recent DomainWave — no selection logic
    dw = waves[-1]

    packet = HydroPacket(
        t=dw.t,
        packet_id=str(uuid.uuid4()),
        lane="domain_probe",
        domain=dw.domain,
        channel=dw.channel,
        value={
            "phase_external": dw.phase_external,
            "phase_field": dw.phase_field,
            "phase_diff": dw.phase_diff,
            "coherence": dw.coherence,
        },
        provenance={
            "source": "manual_domain_to_ingress_probe",
            "domain_wave_ts": dw.t,
            "extractor": dw.extractor,
        },
        # Neutral posture — no authority asserted
        rate=None,
        anomaly_flag=False,
        replay=False,
        phase=dw.phase_diff,
    )

    # Append-only ingress write
    with INGRESS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(packet.__dict__, separators=(",", ":")))
        f.write("\n")

    print(f"PROBE: wrote 1 ingress packet → {INGRESS_PATH}")


if __name__ == "__main__":
    main()
