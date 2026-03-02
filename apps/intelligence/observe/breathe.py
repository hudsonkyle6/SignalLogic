from apps.signal_company_os.adapters.signal_light_press import get_kernel_observables
from apps.signal_company_os.adapters.rhythm_ingest.ingest_envelope import (
    create_envelope,
)
from apps.signal_company_os.adapters.rhythm_ingest.generate_wave import generate_wave


def breathe(lookback_hours: int = 24):
    """
    Manual observational closure.
    Human-triggered.
    No cadence, no authority, no escalation.
    """

    observables = get_kernel_observables(lookback_hours=lookback_hours)

    envelope = create_envelope(
        domain="signal_light_press",
        observables=observables,
        shepherd_posture="SILENT",
    )

    return generate_wave(envelope)


if __name__ == "__main__":
    path = breathe()
    print(f"Wave sealed → {path}")
