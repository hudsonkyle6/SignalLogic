from pathlib import Path
import json
import math

from rhythm_os.core.phasor_merge import project_samples_to_clocks
from rhythm_os.core.domain_clocks.cyber import CYBER_CYCLES

METERS_DIR = Path("src/rhythm_os/data/dark_field/meters")


def read_latest_net_samples():
    files = sorted(METERS_DIR.glob("*.jsonl"))
    if not files:
        return []

    samples = []
    with files[-1].open("r", encoding="utf-8") as f:
        for line in f:
            pkt = json.loads(line)
            if pkt.get("lane") != "net":
                continue

            try:
                t = float(pkt["t"])
                out_bps = float(pkt["data"]["out_rate_bps"])
                samples.append((t, out_bps))
            except Exception:
                continue

    return samples


def main():
    samples = read_latest_net_samples()
    if not samples:
        print("No samples.")
        return

    # -------------------------------------------------
    # Inject synthetic 5-second modulation
    # -------------------------------------------------
    modulated = []
    for t, a in samples:
        a_mod = a * (1.0 + 0.5 * math.sin(2 * math.pi * t / 5.0))
        modulated.append((t, a_mod))

    result = project_samples_to_clocks(modulated, CYBER_CYCLES)

    print("\n--- CYBER CLOCK COHERENCE (5s injected) ---")
    for name, cp in result.clocks.items():
        print(f"{name:12s}  r={cp.coherence:.4f}")

    print("\nGroup coherence:", f"{result.coherence:.4f}")
    print("Group phase:", f"{result.phase:.4f}")


if __name__ == "__main__":
    main()
