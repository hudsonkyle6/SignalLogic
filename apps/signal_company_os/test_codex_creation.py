from .codex import Codex
from pathlib import Path

# Set your root path (adjust if needed)
root = Path(r"C:\Users\SignalADmin\Signal Archive\SignalLogic\rhythm_os\apps\signal_company")

codex = Codex(root)

# Test 1: Doctrine
codex.create(
    name="test_doctrine_20260116",
    text="Preserve by default. Detect before destroying. When detection is impossible without exposure, allow provisional entanglement under constraint. Destroy only in service of what has proven itself.",
    phase=0.0,
    frequency=1.0,
    amplitude=1.0,
    afterglow_decay=0.5,
    couplings={"identity": 0.9, "intelligence": 0.8}
)
print("Test 1 created.")

# Test 2: Scar
codex.create(
    name="test_scar_20260116",
    text="F-6: Preservation Lock — High evidentiary rigor hardens into permanent refusal of exposure, blocking discontinuous renewal. Primary Poison: Honorable fossilization.",
    phase=0.5,
    frequency=0.8,
    amplitude=0.6,
    afterglow_decay=0.7,
    couplings={"rigor": 0.95, "exposure": 0.2}
)
print("Test 2 created.")

# Test 3: Resonance Note
codex.create(
    name="test_resonance_20260116",
    text="Observed load cycle peak at 18:00, solar pulse aligned 12:00–16:00, partial phase coherence detected.",
    phase=0.7,
    frequency=1.2,
    amplitude=0.4,
    afterglow_decay=0.3,
    couplings={"load": 0.75, "solar": 0.65}
)
print("Test 3 created.")
