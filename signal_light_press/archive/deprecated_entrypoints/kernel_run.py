# rhythm_os/core/kernel_run.py
"""
ARCHIVED — Jan 2026

This file served as the headless entrypoint for the
pre-sovereign Rhythm OS kernel pipeline.

Retired when Core was sealed as a passive,
append-only observational substrate.
"""

"""
Rhythm OS — Kernel Runner (Silent)

Purpose:
    Minimal headless entrypoint to advance the core observation state.

Authorities (ONLY):
    • Invoke the kernel engine (run_daily_kernel)
    • Exit silently on success
    • Raise exceptions on failure

Non-authorities:
    • No journaling
    • No Sage/Oracle publishing
    • No prompts
    • No prints/banners
"""

from __future__ import annotations

from rhythm_os.core.kernel import run_daily_kernel


def main() -> None:
    # Silent on success; exceptions propagate on failure.
    run_daily_kernel()


if __name__ == "__main__":
    main()
