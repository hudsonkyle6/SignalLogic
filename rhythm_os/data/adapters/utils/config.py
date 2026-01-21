from typing import Dict


def load_runtime_config() -> Dict[str, str]:
    """
    Load runtime configuration.

    For now, this is intentionally minimal.
    Environment variables or files can be added later.
    """
    return {
        "mode": "daily",
        "environment": "local",
    }
