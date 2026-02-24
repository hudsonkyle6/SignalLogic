

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path

from apps.signal_observatory.tools.emit_market_to_hydro import emit_market_domain
from apps.signal_observatory.tools.emit_natural_to_bus import emit_natural_domain

from signal_core.core.hydro_types import HydroPacket
from signal_core.core.dark_field import append_hydro_ingress_packet
from signal_core.core.run_cycle_once import run_cycle_once

REPO_ROOT = Path(__file__).resolve().parents[3]


def run_daily() -> None:
    t = float(int(time.time()))

    # --------------------------------------------------
    # MARKET
    # --------------------------------------------------
    m = emit_market_domain(window_days=7)
    print(f"[MARKET] emitted {m} waves")

    # --------------------------------------------------
    # NATURAL
    # --------------------------------------------------
    n = emit_natural_domain()
    print(f"[NATURAL] emitted {n} waves")



    # --------------------------------------------------
    # HYDRO — emit ingress marker (pressure only)
    # --------------------------------------------------
    packet = HydroPacket(
        t=t,
        packet_id=str(uuid.uuid4()),
        lane="system",
        domain="system",
        channel="full_daily_run",
        value={"note": "full daily run completed"},
        provenance={"source": "signal_core.full_run_daily"},
        replay=False,
    )

    append_hydro_ingress_packet(packet)
    print("[HYDRO] ingress marker appended")

    # --------------------------------------------------
    # HYDRO — run scanner / dispatcher
    # --------------------------------------------------
    subprocess.run(
        [
            sys.executable,
            "-m",
            "signal_core.core.hydro_ingest_once",
            "--packet-json",
            json.dumps(asdict(packet)),
        ],
        check=True,
    )


    print("[HYDRO] dispatch complete")

    # --------------------------------------------------
    # RHYTHM OS — single canonical cycle
    # --------------------------------------------------
    subprocess.run(
        run_cycle_once(),
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT)},
        check=True,
    )
    print("[CYCLE] reserve + antifragile + alignment complete")
def main() -> None:
    run_daily()


if __name__ == "__main__":
    main()
