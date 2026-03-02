from pathlib import Path
import math

try:
    import pandas as pd
except ImportError as _e:
    raise ImportError(
        "pandas is required for market transform analytics. "
        "Install with: pip install 'signal-logic[analytics]'"
    ) from _e
from typing import List
from datetime import datetime

from rhythm_os.core.field import compute_field
from rhythm_os.domain.domain_wave import DomainWave
from rhythm_os.domain.oracle.hal import measure_alignment


DATA_PATH = Path(__file__).parents[1] / "lanes" / "market" / "data.csv"


def project_market_domain(window_days: int = 7) -> List[DomainWave]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(DATA_PATH)

    df = pd.read_csv(DATA_PATH).tail(window_days)

    waves = []

    sp_lo, sp_hi = df["SP500"].min(), df["SP500"].max()

    for _, row in df.iterrows():
        t = datetime.fromisoformat(row["Date"]).timestamp()

        sp_norm = (row["SP500"] - sp_lo) / (sp_hi - sp_lo)
        external_phase = 2 * math.pi * sp_norm

        field = compute_field(t)

        hal = measure_alignment(
            phase_external_rad=external_phase,
            phase_field_rad=math.atan2(field.composite.imag, field.composite.real),
        )

        waves.append(
            DomainWave(
                t=t,
                domain="market",
                channel="helix_projection",
                field_cycle="computed",
                phase_external=external_phase,
                phase_field=math.atan2(field.composite.imag, field.composite.real),
                phase_diff=hal.phase_diff_rad,
                coherence=field.coherence,
                extractor={
                    "source": "signal_observatory.market",
                    "method": "sp500_normalized",
                    "window_days": window_days,
                    "version": "v1",
                },
            )
        )

    return waves
