from pathlib import Path
from codex import Codex
from exporter import Exporter
from wave import Wave

# Your root path
root = Path(r"C:\Users\SignalADmin\Signal Archive\SignalLogic\rhythm_os\apps\signal_company")

# Create Codex instance
codex = Codex(root)

# Test 1: Doctrine - Create
codex.create(
    name="test_doctrine_cycle",
    text="Preserve by default. Detect before destroying. When detection is impossible without exposure, allow provisional entanglement under constraint. Destroy only in service of what has proven itself.",
    phase=0.0,
    frequency=1.0,
    amplitude=1.0,
    afterglow_decay=0.5,
    couplings={"identity": 0.9, "intelligence": 0.8}
)
print("Test 1: Doctrine wave created.")

# Export to text mirror
exporter = Exporter(root)
exported_txt = exporter.export_codex("test_doctrine_cycle")
print(f"Exported to: {exported_txt}")

# Re-import text to new wave
reimported = codex.reimport_from_text(exported_txt, "test_doctrine_reimported")
print(f"Re-imported wave created: {reimported}")

print("\nCycle complete for Test 1.")
print("Now check files in codex/ and codex_export/ folders.")
print("Open original and re-imported .osc.json — fields should match (except timestamp).")
