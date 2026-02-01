from typing import Iterable
import csv

def export_scope_csv(waves: Iterable, path: str, *, window: int = 120) -> None:
    """
    Export sealed, read-only wave views for visualization only.

    This function performs:
    - No computation
    - No interpretation
    - No mutation
    """

    rows = list(waves)[-window:]

    fields = [
        "t",
        "coherence",
        "phase_spread",
        "buffer_margin",
        "persistence",
        "drift",
        "afterglow",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)

        for w in rows:
            writer.writerow([
                getattr(w, "t", None),
                getattr(w, "coherence", None),
                getattr(w, "phase_spread", None),
                getattr(w, "buffer_margin", None),
                getattr(w, "persistence", None),
                getattr(w, "drift", None),
                getattr(w, "afterglow", None),
            ])
