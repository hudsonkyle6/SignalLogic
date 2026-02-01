from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict

from apps.signal_company_os.forge.infrastructure.interval_mandate import IntervalMandate, is_expired


# --- Whitelisted task registry ---
TASKS: Dict[str, Callable[[IntervalMandate], dict]] = {}


def register_task(name: str):
    def deco(fn: Callable[[IntervalMandate], dict]):
        TASKS[name] = fn
        return fn
    return deco


@register_task("monitor_only")
def task_monitor_only(m: IntervalMandate) -> dict:
    """
    Placeholder task: observe only, no actuation.
    """
    return {
        "task": "monitor_only",
        "status": "ok",
        "note": "observed; no actuation performed"
    }


def run_interval(m: IntervalMandate, *, log_dir: Path) -> Path:
    """
    Executes whitelisted tasks within a granted interval.
    Enforces:
    - time bounds
    - task whitelist
    - automatic expiry
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()

    if now < m.start_ts:
        raise RuntimeError("Mandate not active yet.")
    if is_expired(m, now):
        raise RuntimeError("Mandate expired.")

    results = {
        "mandate_id": m.mandate_id,
        "created_ts": m.created_ts,
        "start_ts": m.start_ts,
        "end_ts": m.end_ts,
        "justification": m.justification,
        "operator_note": m.operator_note,
        "events": [],
    }

    for task_name in m.task_whitelist:
        if is_expired(m):
            results["events"].append({
                "task": task_name,
                "status": "stopped",
                "reason": "interval expired"
            })
            break

        if task_name not in TASKS:
            results["events"].append({
                "task": task_name,
                "status": "blocked",
                "reason": "task not registered"
            })
            continue

        out = TASKS[task_name](m)
        results["events"].append(out)

    out_path = log_dir / f"interval_{m.mandate_id}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    # Minimal manual harness
    now = time.time()
    mandate = IntervalMandate(
        mandate_id="demo_interval",
        created_ts=now,
        start_ts=now,
        end_ts=now + 60,
        domain_scope_whitelist=["core_self"],
        task_whitelist=["monitor_only"],
        justification="demo AUD interval"
    )

    path = run_interval(mandate, log_dir=Path("artifacts/interval_logs"))
    print(f"WROTE: {path}")
