"""
REGISTRY LOADER — CANONICAL
Authority: Signal Light Press
Role: Canonical Registry Intake & Validation
Status: Non-Agentive
"""

from pathlib import Path
import yaml
import sys
from types import MappingProxyType

# -------------------------------------------------
# REGISTRY PATHS (CANONICAL)
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

REGISTRIES = {
    "sage": BASE_DIR / "index" / "sage_registry.yaml",
    # future:
    # "shepherd": BASE_DIR / "index" / "shepherd_registry.yaml",
    # "helmsman": BASE_DIR / "index" / "helmsman_registry.yaml",
}

# -------------------------------------------------
# LOAD & VALIDATE
# -------------------------------------------------

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Registry missing: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load registry {path}: {e}")

def _validate_registry(name: str, registry: dict):
    """
    Minimal structural validation.
    Doctrine validation happens elsewhere.
    """
    if not isinstance(registry, dict):
        raise ValueError(f"{name} registry is not a dictionary")

    if "sage" in name:
        required_keys = ["sage", "read_scope", "constraints", "seal"]
        for key in required_keys:
            if key not in registry:
                raise ValueError(f"Sage registry missing required key: {key}")

# -------------------------------------------------
# PUBLIC API
# -------------------------------------------------

class RegistryLoader:
    """
    Loads and exposes canonical registries as read-only objects.
    """

    def __init__(self):
        self._registries = {}

    def load_all(self):
        for name, path in REGISTRIES.items():
            registry = _load_yaml(path)
            _validate_registry(name, registry)

            # Freeze registry (read-only)
            self._registries[name] = MappingProxyType(registry)

    def get(self, name: str):
        if name not in self._registries:
            raise KeyError(f"Registry not loaded: {name}")
        return self._registries[name]

# -------------------------------------------------
# BOOTSTRAP (OPTIONAL)
# -------------------------------------------------

def load_registries_or_die():
    loader = RegistryLoader()
    try:
        loader.load_all()
    except Exception as e:
        print(f"❌ Registry integrity failure: {e}")
        sys.exit(1)
    return loader
