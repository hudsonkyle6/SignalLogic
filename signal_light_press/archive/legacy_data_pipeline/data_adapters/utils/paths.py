from pathlib import Path
from typing import Dict


def resolve_runtime_paths() -> Dict[str, Path]:
    """
    Resolve all runtime paths for this run.
    No directories are created here.
    """
    root = Path(__file__).resolve().parents[3]

    return {
        "root": root,
        "data": root / "data",
        "logs": root / "data",
        "exports": root / "data" / "exports",
    }
