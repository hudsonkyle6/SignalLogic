from pathlib import Path
from .codex import Codex  # relative import

root = Path(r"C:\Users\SignalADmin\Signal Archive\SignalLogic\rhythm_os\apps\signal_company")
codex = Codex(root)
print("Codex directory:", codex.codex_dir)
print("Exists?", codex.codex_dir.exists())
if codex.codex_dir.exists():
    print("Files in codex dir:", list(codex.codex_dir.iterdir()))
else:
    print("Codex dir does not exist yet.")
