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
        print("ADAPTER: no DomainWaves to emit")
        return

    emitted = 0

    with INGRESS_PATH.open("a", encoding="utf-8") as f:
        for dw in waves:
            packet = HydroPacket(
                t=dw.t,
                packet_id=str(uuid.uuid4()),
                lane="natural",              # ← ADMITTED LANE
                domain=dw.domain,
                channel=dw.channel,
                value={
                    "phase_external": dw.phase_external,
                    "phase_field": dw.phase_field,
                    "phase_diff": dw.phase_diff,
                    "coherence": dw.coherence,
                    "field_cycle": dw.field_cycle,
                },
                provenance={
                    "source": "psr.domain_to_natural_ingress",
                    "domain_wave_ts": dw.t,
                    "extractor": dw.extractor,
                },
                rate=None,
                anomaly_flag=False,
                replay=False,
                phase=dw.phase_diff,
            )

            f.write(json.dumps(packet.__dict__, separators=(",", ":")))
            f.write("\n")
            emitted += 1

    print(f"ADAPTER: emitted {emitted} packets → natural lane ingress")


if __name__ == "__main__":
    main()
