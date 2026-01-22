"""
Signal_Company_OS SEAL
# This renderer is Canonical Posture Interface v1.0
# All outputs must conform to Assist Under Discipline
# Authority: Signal Light Press
# Date: 2026-01-16

Authority: Signal Light Press (Kernel)
Classification: Protected Internal
Mode: Assist Under Discipline (Narrative Only)
Role: Application Layer (Downstream of Engines; Upstream of Humans)
Invariant: 3-4-7 Geometry


This renderer:
- Reads upstream signals (Oracle / Sage / Shepherd)
- Renders a unified posture report for human review
- Does NOT actuate, decide, allocate, optimize, prioritize, or pursue

Outputs:
- Markdown posture report to:
  data/signal_company/posture/posture_report_YYYY-MM-DD.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


# ------------------------------------------------------------
# Paths (CANONICAL)
# ------------------------------------------------------------

@dataclass(frozen=True)
class SignalPaths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def merged(self) -> Path:
        return self.data / "merged"

    @property
    def oracle_dir(self) -> Path:
        return self.data / "oracle"

    @property
    def human_dir(self) -> Path:
        return self.data / "human"

    @property
    def signal_company_dir(self) -> Path:
        return self.data / "signal_company"

    @property
    def posture_dir(self) -> Path:
        return self.signal_company_dir / "posture"

    @property
    def shepherd_posture_snapshot(self) -> Path:
        return self.root / "rhythm_os" / "shepherd" / "runtime" / "shepherd_posture_snapshot.yaml"

    @property
    def sage_state(self) -> Path:
        return self.root / "rhythm_os" / "sage" / "state" / "sage_state.json"

    @property
    def oracle_layer4_csv(self) -> Path:
        return self.oracle_dir / "oracle_layer4.csv"

    @property
    def human_ledger_csv(self) -> Path:
        return self.human_dir / "human_ledger.csv"


# ------------------------------------------------------------
# Utilities (AUD-safe readers)
# ------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_read_json(path: Path):
    if not path.exists():
        return None, f"MISSING: {path}"
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None, f"EMPTY: {path}"
        return json.loads(raw), "OK"
    except Exception as e:
        return None, f"ERROR: {path} ({e})"

def _safe_read_yaml(path: Path):
    if not path.exists():
        return None, f"MISSING: {path}"
    if yaml is None:
        return None, "ERROR: pyyaml not installed"
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None, f"EMPTY: {path}"
        return yaml.safe_load(raw), "OK"
    except Exception as e:
        return None, f"ERROR: {path} ({e})"

def _safe_read_csv(path: Path):
    if not path.exists():
        return None, f"MISSING: {path}"
    try:
        df = pd.read_csv(path)
        if df.empty:
            return None, f"EMPTY: {path}"
        return df, "OK"
    except Exception as e:
        return None, f"ERROR: {path} ({e})"

def _latest_file(folder: Path, prefix: str, suffix: str) -> Optional[Path]:
    if not folder.exists():
        return None
    files = sorted(folder.glob(f"{prefix}*{suffix}"))
    return files[-1] if files else None


# ------------------------------------------------------------
# Unified Posture Object
# ------------------------------------------------------------

@dataclass
class UnifiedPosture:
    anchor_date: str
    generated_utc: str
    sources: Dict[str, str]

    season: Optional[str] = None
    signal_state: Optional[str] = None
    resonance: Optional[float] = None
    amplitude: Optional[float] = None
    resonance_note: Optional[str] = None

    ledger_state: Optional[str] = None
    compass_state: Optional[str] = None

    shepherd_mode: Optional[str] = None
    shepherd_action_allowed: Optional[bool] = None

    sage_kernel_status: Optional[str] = None
    sage_last_run: Optional[str] = None


# ------------------------------------------------------------
# Renderer
# ------------------------------------------------------------

class PostureRenderer:

    def __init__(self, root: Path):
        self.paths = SignalPaths(root)

    def build(self) -> UnifiedPosture:
        sources = {}

        daily_file = _latest_file(self.paths.merged, "daily_", ".csv")
        daily_df, s = _safe_read_csv(daily_file) if daily_file else (None, "MISSING")
        sources["daily_snapshot"] = s

        ledger, s = _safe_read_csv(self.paths.human_ledger_csv)
        sources["human_ledger"] = s

        shepherd, s = _safe_read_yaml(self.paths.shepherd_posture_snapshot)
        sources["shepherd"] = s

        sage, s = _safe_read_json(self.paths.sage_state)
        sources["sage"] = s

        anchor_date = (
            daily_file.stem.replace("daily_", "")
            if daily_file
            else _now_iso().split("T")[0]
        )

        up = UnifiedPosture(
            anchor_date=anchor_date,
            generated_utc=_now_iso(),
            sources=sources,
        )

        if daily_df is not None:
            row = daily_df.iloc[-1]
            up.season = row.get("Season")
            up.signal_state = row.get("State")
            up.resonance = _to_float(row.get("Resonance"))
            up.amplitude = _to_float(row.get("Amplitude"))
            up.resonance_note = row.get("ResonanceNote", None)

        if ledger is not None:
            lr = ledger.iloc[-1]
            up.ledger_state = lr.get("Decision")
            up.compass_state = lr.get("CompassState")

        if shepherd is not None:
            up.shepherd_mode = shepherd.get("posture", {}).get("mode")
            up.shepherd_action_allowed = shepherd.get("permissions", {}).get("action_allowed")

        if sage is not None:
            up.sage_kernel_status = sage.get("status")
            up.sage_last_run = sage.get("last_run")

        return up

    def render_markdown(self, up: UnifiedPosture) -> str:
        degraded = any("MISSING" in v or "ERROR" in v for v in up.sources.values())

        md = [
            "# 📘 Signal_Company_OS — Unified Posture Report",
            "",
            f"**Anchor Day:** {up.anchor_date}",
            f"**Generated (UTC):** {up.generated_utc}",
            "",
            "## Source Health",
            *[f"- **{k}**: {v}" for k, v in up.sources.items()],
            "",
            "## Posture Summary",
            f"- **Season:** {up.season}",
            f"- **Signal State:** {up.signal_state}",
            f"- **Resonance:** {fmt_float(up.resonance)}",
            f"- **Amplitude:** {fmt_float(up.amplitude)}",
            f"- **Resonance Note:** {up.resonance_note or '(none)'}",
            "",
            "## Shepherd",
            f"- **Mode:** {up.shepherd_mode}",
            f"- **Action Allowed:** {up.shepherd_action_allowed}",
            "",
            "## Sage Kernel",
            f"- **Status:** {up.sage_kernel_status}",
            f"- **Last Run:** {up.sage_last_run}",
            "",
            "## Constraints",
            "- Narrative only.",
            "- No actuation, allocation, or pursuit.",
            "- All action remains human.",
        ]

        if degraded:
            md.append("")
            md.append("**Posture Recommendation:** Remain in custodial silence.")
            md.append("Upstream clarity insufficient. Do not act until conditions resolve.")

        return "\n".join(md)

    def run(self) -> Path:
        up = self.build()
        md = self.render_markdown(up)

        self.paths.posture_dir.mkdir(parents=True, exist_ok=True)
        out = self.paths.posture_dir / f"posture_report_{up.anchor_date}.md"
        out.write_text(md, encoding="utf-8")
        return out


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _to_float(v):
    try:
        return float(v)
    except Exception:
        return None

def fmt_float(v, digits=3):
    return "(unknown)" if v is None else f"{v:.{digits}f}"


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def find_signal_logic_root(start: Path) -> Path:
    for p in start.parents:
        if p.name == "SignalLogic":
            return p
    raise RuntimeError("SignalLogic root not found")

def main() -> int:
    root = find_signal_logic_root(Path(__file__).resolve())
    out = PostureRenderer(root).run()
    print(f"✅ Posture report generated → {out}")
    print("ℹ️  Review manually. Silence is lawful when clarity is insufficient.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
