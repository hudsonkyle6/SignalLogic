from pathlib import Path

from rhythm_os.scope.adapters.dark_field_loader import load_dark_field
from rhythm_os.scope.signal_scope_v2 import render_scope


def main() -> None:
    path = Path("src/rhythm_os/data/dark_field/2026-02-07.jsonl")
    waves = load_dark_field(path)
    render_scope(waves)


if __name__ == "__main__":
    main()
