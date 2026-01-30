import time

from rhythm_os.core.field import compute_field, materialize_field_waves
from rhythm_os.adapters.observe.synthetic_multi import (
    SyntheticChannelSpec,
    generate_multi_channel_synthetic,
)
from rhythm_os.domain.oracle.oracle import Oracle
from rhythm_os.domain.oracle.convergence_logic import OracleConvergence
from rhythm_os.ui.signal_dashboard import render_signal_dashboard


def diagnostic_run():
    # ------------------------------------------------------------
    # Time
    # ------------------------------------------------------------
    t_now = time.time()

    # ------------------------------------------------------------
    # Field (this already exists and works)
    # ------------------------------------------------------------
    field_sample = compute_field(t_now)
    field_waves = materialize_field_waves(field_sample)

    # ------------------------------------------------------------
    # Domain waves (synthetic for now)
    # ------------------------------------------------------------
    synthetic_channels = [
        SyntheticChannelSpec(domain="demo", channel="a", freq=1.0),
        SyntheticChannelSpec(domain="demo", channel="b", freq=1.2),
        SyntheticChannelSpec(domain="demo", channel="c", freq=0.8),
    ]

    domain_waves = generate_multi_channel_synthetic(
        t_now=t_now,
        channels=synthetic_channels,
    )

    # ------------------------------------------------------------
    # Oracle (descriptive only)
    # ------------------------------------------------------------
    oracle = Oracle(history_window_hours=24.0)

    oracle_descriptors = oracle.describe(
        t_now=t_now,
        field_waves=field_waves,
        domain_waves=domain_waves,
    )

    convergence_engine = OracleConvergence(
        within_deg=30.0,
        min_channels=2,  # lower for diagnostics
    )

    oracle_convergence = convergence_engine.summarize(
        t_now=t_now,
        descriptors=oracle_descriptors,
    )

    # ------------------------------------------------------------
    # STUBBED authority (explicit, honest)
    # ------------------------------------------------------------
    shepherd_posture = "DIAGNOSTIC_ONLY"

    context = {
        "season": field_sample.season,
        "state": "Still",
    }

    # ------------------------------------------------------------
    # Dashboard (pure presentation)
    # ------------------------------------------------------------
    render_signal_dashboard(
        t=t_now,
        field_sample=field_sample,
        field_waves=field_waves,
        domain_waves=domain_waves,
        oracle_descriptors=oracle_descriptors,
        oracle_convergence=oracle_convergence,
        shepherd_posture=shepherd_posture,
        context=context,
    )


if __name__ == "__main__":
    diagnostic_run()
