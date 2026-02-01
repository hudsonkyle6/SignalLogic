
#!/usr/bin/env python3
"""
Signal Hydro System
Canonical Operational Backbone

Principles:
- Observe honestly
- Propose inertly
- Act only with explicit human gate
- Local-first, auditable, append-only
"""

from __future__ import annotations

import argparse
import json
import os
import time
import datetime as dt
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter
from dataclasses import dataclass, asdict

# Optional network client (OFF by default)
try:
    from polygon import RESTClient
except Exception:
    RESTClient = None


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────

def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today() -> str:
    return dt.date.today().isoformat()

def jdump(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)

def mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    mkdir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(jdump(record) + "\n")

def run(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )


# ──────────────────────────────────────────────────────────────
# Hydro Core
# ──────────────────────────────────────────────────────────────

class HydroAgent:
    def __init__(self, name: str, role: str, model: str):
        self.name = name
        self.role = role
        self.model = model

    def think(self, prompt: str) -> str:
        """
        Placeholder for Ollama / local LLM call.
        Replace with your existing inference hook.
        """
        # For now, inert placeholder
        return json.dumps({
            "agent": self.name,
            "note": "LLM output stub",
            "prompt_hash": hash(prompt)
        })


class SignalHydroSystem:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.primary_model = "qwen2.5:14b"  # example
        self.ops_dir = Path("hydro_ops")

        mkdir(self.ops_dir / "packets")
        mkdir(self.ops_dir / "logs")
        mkdir(self.ops_dir / "digests")

    def process_signal(self, signal: str, human_requested_action: bool = False) -> str:
        """
        Core invariant:
        - Always allowed to observe + propose
        - Never acts unless explicitly gated
        """
        record = {
            "t": now(),
            "signal": signal,
            "human_requested_action": human_requested_action,
            "status": "observed"
        }
        append_jsonl(self.ops_dir / "logs" / "signals.jsonl", record)

        return f"[HYDRO] signal observed ({len(signal)} chars)"


# ──────────────────────────────────────────────────────────────
# Observation Packet
# ──────────────────────────────────────────────────────────────

@dataclass
class OpsPacket:
    t: str
    kind: str
    payload: Dict[str, Any]
    evidence: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────
# Finance Agent
# ──────────────────────────────────────────────────────────────

class FinanceAgent(HydroAgent):
    def __init__(self, model: str, allow_network: bool):
        super().__init__("FinanceAgent", "Observe budgets & markets", model)
        self.allow_network = allow_network

    def track_budget(self, path: Path) -> OpsPacket:
        payload = {"status": "ok"}
        evidence = {"file": str(path)}

        if not path.exists():
            payload["status"] = "missing"
            return OpsPacket(now(), "finance", payload, evidence)

        data = json.loads(path.read_text())
        planned = data.get("planned", 0)
        actual = data.get("actual", 0)

        payload.update({
            "planned": planned,
            "actual": actual,
            "variance": actual - planned
        })

        return OpsPacket(now(), "finance", payload, evidence)

    def track_stocks(self, tickers: List[str]) -> OpsPacket:
        payload = {"tickers": tickers, "status": "skipped"}
        evidence = {}

        if not self.allow_network or RESTClient is None:
            payload["note"] = "network disabled"
            return OpsPacket(now(), "finance", payload, evidence)

        api_key = os.getenv("POLYGON_API_KEY") or os.getenv("MASSIVE_API_KEY")
        if not api_key:
            payload["status"] = "error"
            payload["note"] = "missing API key"
            return OpsPacket(now(), "finance", payload, evidence)

        client = RESTClient(api_key=api_key)
        quotes = {}
        for t in tickers:
            quotes[t] = client.get_last_quote(t)

        payload.update({"status": "ok", "quotes": quotes})
        evidence["provider"] = "polygon"
        return OpsPacket(now(), "finance", payload, evidence)


# ──────────────────────────────────────────────────────────────
# File Agent
# ──────────────────────────────────────────────────────────────

class FileAgent(HydroAgent):
    def __init__(self, model: str):
        super().__init__("FileAgent", "Observe filesystem & git", model)

    def scan(self, root: Path) -> OpsPacket:
        payload = {}
        evidence = {}

        files = [p for p in root.rglob("*") if p.is_file()]
        payload["total_files"] = len(files)
        payload["recent"] = sorted(
            [str(p.relative_to(root)) for p in files],
            key=lambda x: (root / x).stat().st_mtime,
            reverse=True
        )[:10]
        payload["extensions"] = dict(Counter(p.suffix for p in files))

        if (root / ".git").exists():
            payload["git_status"] = run(
                ["git", "status", "--porcelain"], root
            ).stdout.splitlines()
            evidence["git"] = True

        return OpsPacket(now(), "files", payload, evidence)


# ──────────────────────────────────────────────────────────────
# Task Agent
# ──────────────────────────────────────────────────────────────

class TaskAgent(HydroAgent):
    def __init__(self, model: str):
        super().__init__("TaskAgent", "Synthesize tasks", model)

    def generate(self, context: Dict[str, Any]) -> OpsPacket:
        raw = self.think(jdump(context))
        payload = {"raw": raw}
        return OpsPacket(now(), "tasks", payload, {"source": "llm"})


# ──────────────────────────────────────────────────────────────
# Attach Ops Agents
# ──────────────────────────────────────────────────────────────

def attach_company_ops(system: SignalHydroSystem, allow_network: bool):
    system.finance_agent = FinanceAgent(system.primary_model, allow_network)
    system.file_agent = FileAgent(system.primary_model)
    system.task_agent = TaskAgent(system.primary_model)


# ──────────────────────────────────────────────────────────────
# Daemon
# ──────────────────────────────────────────────────────────────

class HydroDaemon:
    def __init__(
        self,
        system: SignalHydroSystem,
        repo_root: Path,
        tick_minutes: int,
        daily_at: str,
    ):
        self.system = system
        self.repo_root = repo_root
        self.tick = tick_minutes * 60
        self.daily_at = daily_at
        self.last_daily: Optional[str] = None

    def run(self):
        print("[HYDRO] daemon running")
        while True:
            packets: List[OpsPacket] = []

            packets.append(
                self.system.file_agent.scan(self.repo_root)
            )

            budget_path = Path("config/budget.json")
            packets.append(
                self.system.finance_agent.track_budget(budget_path)
            )

            for p in packets:
                append_jsonl(
                    self.system.ops_dir / "packets" / f"{today()}.jsonl",
                    p.as_dict()
                )

            # Daily digest
            if self.last_daily != today():
                ctx = {"packets": [p.as_dict() for p in packets]}
                tasks = self.system.task_agent.generate(ctx)
                append_jsonl(
                    self.system.ops_dir / "packets" / f"{today()}.jsonl",
                    tasks.as_dict()
                )

                out = self.system.process_signal(
                    "DAILY_DIGEST\n" + jdump(ctx),
                    human_requested_action=False
                )

                (self.system.ops_dir / "digests").mkdir(exist_ok=True)
                (self.system.ops_dir / "digests" / f"{today()}.md").write_text(
                    f"# Hydro Daily Digest\n\n{out}\n",
                    encoding="utf-8"
                )

                self.last_daily = today()

            time.sleep(self.tick)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser("Signal Hydro System")

    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--tick-minutes", type=int, default=60)
    ap.add_argument("--daily-at", type=str, default="06:30")
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--repo-root", type=str, default=".")

    args = ap.parse_args()

    system = SignalHydroSystem(Path(args.repo_root).resolve())
    attach_company_ops(system, allow_network=args.allow_network)

    if args.daemon:
        d = HydroDaemon(
            system,
            system.repo_root,
            args.tick_minutes,
            args.daily_at
        )
        d.run()
        return

    # One-shot mode
    system.process_signal("MANUAL_RUN", False)
    print("[HYDRO] one-shot run complete")


if __name__ == "__main__":
    main()
