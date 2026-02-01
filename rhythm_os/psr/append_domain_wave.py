# NOTE: This function must never create paths, retry writes, or infer intent.

from pathlib import Path
from rhythm_os.psr.domain_wave import DomainWave


def append_domain_wave(path: Path, wave: DomainWave) -> None:
    """
    Append DomainWave to a JSONL file.

    - Append-only
    - No overwrite
    - No mutation
    - No eager directory creation

    Raises:
        FileNotFoundError: If parent directory does not exist
            (caller must bootstrap persistence structure).
        ValueError: If path exists but is not a regular file.
    """

    if not path.parent.exists():
        raise FileNotFoundError(
            f"Persistence path does not exist: {path.parent}"
        )

    if path.exists() and not path.is_file():
        raise ValueError(f"Path exists but is not a regular file: {path}")

    with path.open("a", encoding="utf-8") as f:
        f.write(wave.to_json())
        f.write("\n")
