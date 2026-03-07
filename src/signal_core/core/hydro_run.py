#!/usr/bin/env python3
"""
Signal Hydro — ML Inference Hook + Health Check
POSTURE: OBSERVATORY

_run_ml_inference: called by hydro_run_cadence.__main__ after each cycle.
_health_check:     used by the --health CLI flag below.

The full multi-domain cycle is orchestrated by apps/run_cycle_once.py.
"""

from __future__ import annotations

import dataclasses
import sys

from signal_core.core.log import configure, get_logger
from signal_core.core.hydro_run_cadence import CycleResult

configure()
log = get_logger(__name__)


def _run_ml_inference(result: "CycleResult", features: dict) -> "CycleResult":
    """
    Run classifier inference on the current cycle's features.

    Returns the result with ml_prediction populated if a trained model
    is available, or the original result unchanged when:
      - no model has been trained yet (silent — model is optional)
      - features dict is empty (feature extraction failed upstream)
      - any other exception (logged as warning, cycle is never blocked)

    This function is extracted to allow direct unit testing without
    spinning up the full hydro cycle.
    """
    if not features:
        return result
    try:
        from signal_core.core.ml.classifier import load_model, predict

        if load_model() is None:
            return result
        pred = predict(features)
        log.info(
            "ml prediction label=%s confidence=%.1f%% model=%s",
            pred.predicted_label,
            pred.confidence * 100,
            pred.model_version,
        )
        return dataclasses.replace(
            result,
            ml_prediction={
                "predicted_label": pred.predicted_label,
                "confidence": pred.confidence,
                "probabilities": pred.probabilities,
                "model_version": pred.model_version,
                "calibrated": pred.calibrated,
            },
        )
    except Exception:
        log.warning("ml inference failed — cycle result unaffected", exc_info=True)
        return result


def run_cycle_once() -> None:
    """Run one observation cycle (observe → gate → enqueue → dispatch)."""
    from signal_core.core.run_cycle_once import run_cycle_once as _inner

    _inner()


def _hydro_daily() -> "CycleResult":
    """Run the hydro gate/dispatch/commit/turbine/ML pipeline."""
    from signal_core.core.hydro_run_cadence import main

    return main()


def run_full_cycle() -> "CycleResult":
    """
    Run a complete SignalLogic cycle: observe → drain/commit → helm.

    Attaches the helm recommendation to the returned CycleResult and
    appends one record to the trust ledger.  Helm errors never block
    the cycle — result is returned regardless.
    """
    run_cycle_once()
    result = _hydro_daily()
    try:
        from rhythm_os.domain.helm.engine import compute_helm
        from rhythm_os.domain.helm.ledger import append_helm_record, record_from_helm_result

        h = compute_helm(result)
        result = dataclasses.replace(
            result,
            helm={"state": h.state, "rationale": h.rationale, "ts": h.ts},
        )
        append_helm_record(record_from_helm_result(h, cycle_ts=result.cycle_ts))
        log.info("helm recommendation state=%s", h.state)
    except Exception:
        log.warning("helm attachment failed in run_full_cycle", exc_info=True)
    return result


def _health_check() -> int:
    """Return 0 if system is warm/ready, 1 if cold/degraded, 2 on error."""
    try:
        from rhythm_os.runtime.readiness import check_readiness
        from rhythm_os.runtime.deploy_config import get_baseline_requirements

        status = check_readiness(**get_baseline_requirements())
        return 0 if status.overall_ready else 1
    except Exception:
        log.exception("health check failed")
        return 2


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="SignalLogic — health check")
    ap.add_argument(
        "--health",
        action="store_true",
        help="check system readiness and exit 0 (warm), 1 (cold), 2 (error)",
    )
    args = ap.parse_args()

    if args.health:
        sys.exit(_health_check())

    ap.print_help()


if __name__ == "__main__":
    main()
