from pathlib import Path

# Root directory = current working directory
ROOT = Path.cwd()

# Helper functions
def mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()

# -------------------------------
# CORE
# -------------------------------
mkdir(ROOT / "core")
touch(ROOT / "core" / "registry_loader.py")

# -------------------------------
# INDEX
# -------------------------------
mkdir(ROOT / "index" / "manifests")
touch(ROOT / "index" / "sage_registry.yaml")

# -------------------------------
# LAWS
# -------------------------------
mkdir(ROOT / "laws")
for law in [
    "sage_law.md",
    "boundary_law.md",
    "integrity_law.md",
    "alignment_law.md",
    "rhythm_law.md",
    "seasonal_law.md",
    "archive_law.md",
    "operator_law.md",
]:
    touch(ROOT / "laws" / law)

# -------------------------------
# LEDGER (INTENT ONLY)
# -------------------------------
mkdir(ROOT / "ledger")
for ledger_file in [
    "annual_arc.yaml",
    "seasonal_arc.yaml",
    "weekly_intent.yaml",
    "daily_intent.yaml",
    "backlog.yaml",
]:
    touch(ROOT / "ledger" / ledger_file)

# -------------------------------
# CONSOLE
# -------------------------------
mkdir(ROOT / "console" / "prompts")
for script in [
    "morning_brief.py",
    "daily_report.py",
    "end_of_day.py",
]:
    touch(ROOT / "console" / script)

# -------------------------------
# ARCHIVE
# -------------------------------
mkdir(ROOT / "archive" / "doctrine" / "philosophy")
mkdir(ROOT / "archive" / "doctrine" / "equations")
mkdir(ROOT / "archive" / "doctrine" / "constants")
mkdir(ROOT / "archive" / "doctrine" / "HST")
mkdir(ROOT / "archive" / "documents")
mkdir(ROOT / "archive" / "financial")
mkdir(ROOT / "archive" / "maps")
mkdir(ROOT / "archive" / "logs")
mkdir(ROOT / "archive" / "snapshots")

# -------------------------------
# RHYTHMS (MIRRORS + ANNOTATIONS ONLY)
# -------------------------------
mkdir(ROOT / "rhythms" / "mirrors")
mkdir(ROOT / "rhythms" / "annotations")

touch(ROOT / "rhythms" / "harmony_notes.md")
for mirror in [
    "oracle_hst_mirror.csv",
    "oracle_phase_mirror.csv",
    "oracle_resonance_mirror.csv",
]:
    touch(ROOT / "rhythms" / "mirrors" / mirror)

# -------------------------------
# ORACLE LINK (READ-ONLY)
# -------------------------------
mkdir(ROOT / "oracle_link")
for oracle_file in [
    "oracle_snapshot.json",
    "resonance_feed.csv",
    "amplitude_feed.csv",
    "hst_feed.csv",
    "schema_version.txt",
]:
    touch(ROOT / "oracle_link" / oracle_file)

# -------------------------------
# SHEPHERD LINK (DORMANT)
# -------------------------------
mkdir(ROOT / "shepherd_link")
touch(ROOT / "shepherd_link" / "README.md")

# -------------------------------
# PROCESSES (REFLECTION ONLY)
# -------------------------------
mkdir(ROOT / "processes")
for process in [
    "daily_reflection.py",
    "weekly_reflection.py",
    "seasonal_reflection.py",
    "archive_cleaner.py",
    "consistency_auditor.py",
]:
    touch(ROOT / "processes" / process)

# -------------------------------
# STATE (EPHEMERAL)
# -------------------------------
mkdir(ROOT / "state")
for state_file in [
    "sage_state.json",
    "drift_index.csv",
    "readiness_index.csv",
    "system_health.csv",
    "TTL.md",
]:
    touch(ROOT / "state" / state_file)

print("✅ SageOS canonical v1.0 scaffold created / verified.")
