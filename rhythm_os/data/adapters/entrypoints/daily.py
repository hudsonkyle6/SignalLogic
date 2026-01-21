"""
Rhythm OS — Daily Entrypoint (Phase I)

This file is intentionally thin.
It wires stage functions in order and exits.

No logic.
No rendering.
No journaling.
No scheduling.
"""

from rhythm_os.adapters.orchestration.stages import (
    bootstrap_runtime,
    ingest_inputs,
    normalize_inputs,
    derive_signals,
    mint_waves,
    append_dark_field,
    domain_pass,
    project_artifacts,
    emit_outputs,
    close_run,
)


def run() -> None:
    """Execute a single governed daily cycle."""
    context = bootstrap_runtime()
    raw_inputs = ingest_inputs(context)
    normalized = normalize_inputs(raw_inputs, context)
    derived = derive_signals(normalized, context)
    waves = mint_waves(derived, context)
    append_dark_field(waves, context)
    domain_state = domain_pass(waves, context)
    artifacts = project_artifacts(domain_state, context)
    emit_outputs(artifacts, context)
    close_run(context)


if __name__ == "__main__":
    run()
