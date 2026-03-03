import time
import math
import json
import random

from rhythm_os.runtime.paths import METERS_DIR

OUT_FILE = METERS_DIR / "simulated_pressure.jsonl"


def main():
    METERS_DIR.mkdir(parents=True, exist_ok=True)

    print("Simulating aggressive multi-band pressure for 90 seconds...")

    start = time.time()

    with OUT_FILE.open("w", encoding="utf-8") as f:
        while time.time() - start < 90:
            t = time.time()

            # 1s square-wave burst
            burst_1s = 2_000_000 if int(t) % 2 == 0 else 0

            # 5s sinusoidal modulation
            mod_5s = 500_000 * math.sin(2 * math.pi * t / 5.0)

            # Random spike noise
            chaos = 3_000_000 if random.random() < 0.15 else 0

            # Slow 15s roll
            roll_15s = 800_000 * math.sin(2 * math.pi * t / 15.0)

            pulse = burst_1s + mod_5s + chaos + roll_15s

            pkt = {
                "t": t,
                "lane": "net",
                "data": {
                    "in_rate_bps": 0.0,
                    "out_rate_bps": max(pulse, 0.0),
                    "turbidity_out": 0.0,
                },
            }

            f.write(json.dumps(pkt) + "\n")
            f.flush()

            time.sleep(0.02)

    print("Simulation complete.")


if __name__ == "__main__":
    main()
