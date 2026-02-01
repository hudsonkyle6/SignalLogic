from __future__ import annotations

import argparse
from pathlib import Path

from .lib.policy import load_policy
from .lib.observe import run_observe
from .lib.propose import run_propose
from .lib.apply import run_apply
from .lib.homecoming import run_homecoming

def main() -> int:
    parser = argparse.ArgumentParser(prog="signal_control_plane")
    parser.add_argument("cmd", choices=["observe", "propose", "apply", "homecoming"])
    parser.add_argument("--root", default=None, help="Override root (absolute path).")
    parser.add_argument("--policy", default="apps/signal_company_os/control_plane/policy.yaml")
    parser.add_argument("--out", default="apps/signal_company_os/control_plane/reports")
    parser.add_argument("--plan", default=None, help="Plan path for apply.")
    parser.add_argument("--scope", default="slp+git", help="propose scope: slp, git, slp+git")
    parser.add_argument("--mode", default="production", choices=["production", "lab"])
    args = parser.parse_args()

    policy = load_policy(Path(args.policy))

    if args.cmd == "observe":
        return run_observe(policy, out_dir=Path(args.out), mode=args.mode, root_override=args.root)
    if args.cmd == "propose":
        return run_propose(policy, out_dir=Path(args.out), mode=args.mode, root_override=args.root, scope=args.scope)
    if args.cmd == "apply":
        if not args.plan:
            raise SystemExit("--plan is required for apply")
        return run_apply(policy, plan_path=Path(args.plan), mode=args.mode, root_override=args.root)
    if args.cmd == "homecoming":
        return run_homecoming(policy)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
