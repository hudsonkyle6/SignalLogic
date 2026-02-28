#!/usr/bin/env python3
"""
SignalLogic Helix Dashboard

Visualizes the three-tier signature architecture as a rotating double helix:

  Tier III  DOMAIN   (top, cyan)    — application-specific signals
  Tier II   NATURAL  (mid, green)   — environmental baseline
  Tier I    SYSTEM   (bot, yellow)  — machine telemetry baseline

Each strand of the helix carries one tier. The helix rotates in watch mode
as new cycles complete, showing signal flow from system → natural → domain.

Usage:
    python -m signal_core.core.dashboard.helix_dashboard           # snapshot
    python -m signal_core.core.dashboard.helix_dashboard --watch   # live, 5s refresh
    python -m signal_core.core.dashboard.helix_dashboard --animate # rotating helix
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.columns import Columns
    from rich.align import Align
    from rich.rule import Rule
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

from rhythm_os.runtime.paths import METERS_DIR, NATURAL_DIR, PENSTOCK_DIR, TURBINE_DIR
from rhythm_os.runtime.readiness import check_readiness, ReadinessStatus
from rhythm_os.runtime.deploy_config import (
    get_deployment_name,
    get_location,
    get_domain_channels,
    get_baseline_requirements,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data readers (stateless — reads from today's JSONL files)
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_last_n(directory: Path, n: int = 5) -> List[Dict[str, Any]]:
    path = directory / f"{_today()}.jsonl"
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return records[-n:] if n > 0 else records


def _count_today(directory: Path) -> int:
    path = directory / f"{_today()}.jsonl"
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _load_last_cycle_result(penstock_dir: Path) -> Optional[Dict[str, Any]]:
    """Read the most recent record from today's penstock for cycle stats."""
    records = _read_last_n(penstock_dir, n=1)
    return records[0] if records else None


# ─────────────────────────────────────────────────────────────────────────────
# Helix renderer
# ─────────────────────────────────────────────────────────────────────────────

# Characters for helix strand depth
_FRONT  = "●"
_BACK   = "○"
_RUNG   = "─"
_CROSS  = "◆"

# Tier zones (fraction of total height, top-to-bottom on screen)
# Screen y=0 is top → Domain is drawn first (top), System last (bottom)
_TIERS = [
    (0.00, 0.33, "bold cyan",   "dim cyan",   "III", "DOMAIN"),
    (0.33, 0.67, "bold green",  "dim green",  "II",  "NATURAL"),
    (0.67, 1.00, "bold yellow", "dim yellow", "I",   "SYSTEM"),
]


def _tier_style(y_frac: float) -> Tuple[str, str]:
    """Return (front_style, back_style) for a given vertical fraction."""
    for lo, hi, front, back, *_ in _TIERS:
        if lo <= y_frac < hi:
            return front, back
    return "bold yellow", "dim yellow"


def render_helix(
    height: int = 36,
    width: int = 28,
    turns: float = 3.0,
    rotation: float = 0.0,
) -> List["Text"]:
    """
    Render one frame of the double helix.
    Returns a list of rich Text objects (one per row, exactly `width` wide).
    """
    if not _HAS_RICH:
        return []

    half_w = width // 2
    radius = max(3, (width // 2) - 3)
    # Rung every half-turn
    rung_interval = max(2, int(height / (turns * 2)))

    rows: List[Text] = []

    for y in range(height):
        y_frac = y / max(1, height - 1)
        theta = y_frac * turns * 2 * math.pi + rotation

        # Strand positions
        x_a = round(half_w + radius * math.sin(theta))
        x_b = round(half_w - radius * math.sin(theta))  # π offset

        # Z depth: positive = front (closer to viewer)
        z_a = math.cos(theta)

        front_style, back_style = _tier_style(y_frac)

        # Build character grid
        row: List[Tuple[str, str]] = [(" ", "")] * width

        # Draw rung at interval
        if y % rung_interval == 0:
            xa, xb = sorted([max(0, x_a), min(width - 1, x_b)])
            for x in range(xa, xb + 1):
                row[x] = (_RUNG, front_style)

        # Draw strand A
        if 0 <= x_a < width:
            char = _FRONT if z_a >= 0 else _BACK
            style = front_style if z_a >= 0 else back_style
            row[x_a] = (char, style)

        # Draw strand B (always opposite z-depth to A)
        if 0 <= x_b < width:
            char = _FRONT if z_a < 0 else _BACK
            style = front_style if z_a < 0 else back_style
            row[x_b] = (char, style)

        # Build rich Text for this row
        line = Text(no_wrap=True)
        for ch, st in row:
            if st:
                line.append(ch, style=st)
            else:
                line.append(ch)

        rows.append(line)

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Bar helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 12, style_full: str = "green", style_empty: str = "grey50") -> "Text":
    filled = round(max(0.0, min(1.0, value)) * width)
    bar = Text()
    bar.append("█" * filled, style=style_full)
    bar.append("░" * (width - filled), style=style_empty)
    return bar


def _ready_badge(ready: bool) -> "Text":
    if ready:
        return Text(" WARM ", style="bold black on green")
    return Text(" COLD ", style="bold white on red")


# ─────────────────────────────────────────────────────────────────────────────
# Tier panels
# ─────────────────────────────────────────────────────────────────────────────

def _panel_system(readiness: ReadinessStatus) -> Panel:
    meter_records = _read_last_n(METERS_DIR, n=1)
    last = meter_records[0] if meter_records else {}
    data = last.get("data", {})

    cpu_pct = data.get("cpu_percent_mean", data.get("cur_norm_0_1", None))
    mem_pct = data.get("mem_percent", None)
    cpu_mhz = data.get("cur_mhz_mean", None)
    in_bps  = data.get("in_rate_bps", None)
    out_bps = data.get("out_rate_bps", None)
    count   = readiness.system_count

    t = Table.grid(padding=(0, 1))
    t.add_column(width=10, no_wrap=True)
    t.add_column(width=16, no_wrap=True)
    t.add_column(no_wrap=True)

    if cpu_pct is not None:
        pct = float(cpu_pct)
        bar = _bar(pct / 100.0, style_full="yellow", style_empty="grey23")
        t.add_row("CPU", bar, Text(f"{pct:.1f}%", style="yellow"))
    else:
        t.add_row("CPU", Text("no data yet", style="dim"), Text(""))

    if mem_pct is not None:
        pct = float(mem_pct)
        bar = _bar(pct / 100.0, style_full="yellow", style_empty="grey23")
        t.add_row("Memory", bar, Text(f"{pct:.1f}%", style="yellow"))

    if cpu_mhz is not None:
        t.add_row("CPU MHz", Text(f"{cpu_mhz:.0f} MHz", style="dim yellow"), Text(""))

    if in_bps is not None and out_bps is not None:
        net_text = Text(f"↓ {in_bps/1e6:.2f} MB/s  ↑ {out_bps/1e6:.2f} MB/s", style="dim yellow")
        t.add_row("Network", net_text, Text(""))

    t.add_row("", Text(""), Text(""))
    ready_line = Text()
    ready_line.append(f"Records today: {count}  ")
    ready_line.append_text(_ready_badge(readiness.system_ready))
    t.add_row("", ready_line, Text(""))

    return Panel(t, title="[bold yellow]TIER I: SYSTEM[/]", border_style="yellow")


def _panel_natural(readiness: ReadinessStatus) -> Panel:
    lat, lon, label = get_location()
    nat_records = _read_last_n(NATURAL_DIR, n=4)

    pressure_rec = next((r for r in reversed(nat_records) if r.get("channel") == "helix_projection"), None)
    thermal_rec  = next((r for r in reversed(nat_records) if r.get("channel") == "thermal"), None)

    t = Table.grid(padding=(0, 1))
    t.add_column(width=12, no_wrap=True)
    t.add_column(width=20, no_wrap=True)
    t.add_column(no_wrap=True)

    t.add_row("Location", Text(f"{label}", style="bold green"), Text(f"({lat:.4f}°N, {abs(lon):.4f}°{'W' if lon < 0 else 'E'})", style="dim"))

    if pressure_rec:
        d = pressure_rec.get("data", {}) or pressure_rec.get("raw", {})
        raw = pressure_rec.get("raw", {})
        p_hpa = raw.get("pressure_hpa", None)
        pf = d.get("phase_field", None)
        coherence = d.get("coherence", None)
        bar = _bar(float(pf) if pf is not None else 0.0, style_full="green", style_empty="grey23")
        label_txt = f"{p_hpa:.1f} hPa" if p_hpa else "—"
        phase_txt = f"phase={pf:.3f}" if pf is not None else ""
        coh_txt   = f"coh={coherence:.2f}" if coherence is not None else ""
        t.add_row("Pressure", bar, Text(f"{label_txt}  {phase_txt}  {coh_txt}", style="green"))
    else:
        t.add_row("Pressure", Text("no data yet", style="dim"), Text(""))

    if thermal_rec:
        d = thermal_rec.get("data", {}) or thermal_rec.get("raw", {})
        raw = thermal_rec.get("raw", {})
        t_c = raw.get("temperature_c", None)
        pf = d.get("phase_field", None)
        bar = _bar(float(pf) if pf is not None else 0.0, style_full="green", style_empty="grey23")
        label_txt = f"{t_c:.1f}°C" if t_c is not None else "—"
        phase_txt = f"phase={pf:.3f}" if pf is not None else ""
        t.add_row("Temperature", bar, Text(f"{label_txt}  {phase_txt}", style="green"))
    else:
        t.add_row("Temperature", Text("no data yet", style="dim"), Text(""))

    t.add_row("", Text(""), Text(""))
    ready_line = Text()
    ready_line.append(f"Records today: {readiness.natural_count}  ")
    ready_line.append_text(_ready_badge(readiness.natural_ready))
    t.add_row("", ready_line, Text(""))

    return Panel(t, title="[bold green]TIER II: NATURAL[/]", border_style="green")


def _panel_domain() -> Panel:
    channels = get_domain_channels()
    turbine_count = _count_today(TURBINE_DIR)
    penstock_count = _count_today(PENSTOCK_DIR)

    t = Table.grid(padding=(0, 1))
    t.add_column(width=18, no_wrap=True)
    t.add_column(no_wrap=True)

    if channels:
        t.add_row("Channels", Text(", ".join(channels), style="cyan"))
    else:
        t.add_row("Channels", Text("none configured", style="dim"))
        t.add_row("", Text("Add to deployment.yaml → domain.channels", style="dim cyan"))

    t.add_row("Penstock today", Text(str(penstock_count), style="bold cyan"))
    t.add_row("Turbine today",  Text(str(turbine_count),  style="cyan"))

    return Panel(t, title="[bold cyan]TIER III: DOMAIN[/]", border_style="cyan")


def _panel_cycle(cycle_result: Optional[Any] = None) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(width=16, no_wrap=True)
    t.add_column(no_wrap=True)

    if cycle_result is None:
        t.add_row("Status", Text("Awaiting first full cycle…", style="dim"))
    else:
        ts = datetime.fromtimestamp(cycle_result.cycle_ts, tz=timezone.utc).strftime("%H:%M:%S UTC")
        t.add_row("Timestamp",   Text(ts, style="bold white"))
        t.add_row("Drained",     Text(str(cycle_result.packets_drained), style="white"))
        t.add_row("Committed",   Text(str(cycle_result.committed),       style="bold green"))
        t.add_row("Rejected",    Text(str(cycle_result.rejected),        style="red" if cycle_result.rejected else "dim"))
        t.add_row("Turbine obs", Text(str(cycle_result.turbine_obs),     style="cyan"))
        t.add_row("Quarantined", Text(str(cycle_result.spillway_quarantined), style="red" if cycle_result.spillway_quarantined else "dim"))

        cs = cycle_result.convergence_summary
        if cs:
            ev     = cs.get("convergence_event_count", 0)
            strong = cs.get("strong_events", 0)
            t.add_row("Convergence", Text(f"{ev} events ({strong} strong)", style="magenta"))

        bs = cycle_result.baseline_status
        if bs:
            line = Text()
            line.append("System: ")
            line.append_text(_ready_badge(bs.system_ready))
            line.append("  Natural: ")
            line.append_text(_ready_badge(bs.natural_ready))
            t.add_row("Baseline",  line)

    return Panel(t, title="[bold white]LAST CYCLE[/]", border_style="white")


# ─────────────────────────────────────────────────────────────────────────────
# Main layout builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_display(
    rotation: float = 0.0,
    cycle_result: Optional[Any] = None,
) -> "Table":
    """Build the full dashboard as a rich Table (two columns: helix + panels)."""
    if not _HAS_RICH:
        raise RuntimeError("rich is required: pip install rich")

    reqs     = get_baseline_requirements()
    readiness = check_readiness(**reqs)

    # ── Header ──────────────────────────────────────────────────────────────
    name = get_deployment_name()
    lat, lon, label = get_location()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    header = Text(justify="center")
    header.append("◉ ", style="bold magenta")
    header.append(name.upper(), style="bold white")
    header.append("  ●  Helix Observatory  ●  ", style="dim white")
    header.append(label, style="bold cyan")
    header.append(f"  ●  {now_utc}", style="dim white")

    # ── Helix ───────────────────────────────────────────────────────────────
    helix_rows = render_helix(height=36, width=26, turns=3.0, rotation=rotation)

    helix_col = Text()
    for row in helix_rows:
        helix_col.append_text(row)
        helix_col.append("\n")

    # Tier legend below helix
    legend = Text(justify="left")
    legend.append("\n")
    for _, _, front, _, num, name_tier in _TIERS:
        legend.append(f"  {_FRONT} ", style=front)
        legend.append(f"Tier {num}: ", style="dim")
        legend.append(f"{name_tier}\n", style=front)

    helix_text = Text()
    helix_text.append_text(helix_col)
    helix_text.append_text(legend)

    helix_panel = Panel(helix_text, title="[bold magenta]HELIX[/]", border_style="magenta", width=30)

    # ── Right panels ─────────────────────────────────────────────────────────
    p_domain  = _panel_domain()
    p_natural = _panel_natural(readiness)
    p_system  = _panel_system(readiness)
    p_cycle   = _panel_cycle(cycle_result)

    # ── Outer grid ──────────────────────────────────────────────────────────
    outer = Table.grid(expand=True)
    outer.add_column(width=30, no_wrap=False)
    outer.add_column(ratio=1)

    from rich.console import Group

    right = Group(
        Panel(header, border_style="magenta"),
        p_domain,
        p_natural,
        p_system,
        p_cycle,
    )

    outer.add_row(helix_panel, right)
    return outer


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry points
# ─────────────────────────────────────────────────────────────────────────────

def run_snapshot(cycle_result: Optional[Any] = None) -> None:
    """Print one static frame of the dashboard."""
    if not _HAS_RICH:
        _fallback_print()
        return
    console = Console()
    console.print(_build_display(rotation=0.0, cycle_result=cycle_result))


def run_watch(interval: float = 5.0, cycle_result: Optional[Any] = None) -> None:
    """Live dashboard that refreshes every `interval` seconds."""
    if not _HAS_RICH:
        _fallback_print()
        return
    console = Console()
    rotation = 0.0
    with Live(console=console, refresh_per_second=4, screen=True) as live:
        while True:
            live.update(_build_display(rotation=rotation, cycle_result=cycle_result))
            time.sleep(interval)
            rotation += 0.3  # advance helix rotation each refresh


def run_animate(fps: float = 8.0) -> None:
    """
    Continuously rotating helix with data panels.
    Refresh rate governed by `fps`.
    """
    if not _HAS_RICH:
        _fallback_print()
        return
    console = Console()
    rotation = 0.0
    interval = 1.0 / fps
    with Live(console=console, refresh_per_second=fps, screen=True) as live:
        while True:
            live.update(_build_display(rotation=rotation))
            time.sleep(interval)
            rotation += 0.08  # smooth rotation per frame


def _fallback_print() -> None:
    """Plain-text fallback when rich is not installed."""
    reqs     = get_baseline_requirements()
    readiness = check_readiness(**reqs)
    name     = get_deployment_name()
    lat, lon, label = get_location()
    print(f"\n{'='*60}")
    print(f"  {name} — Helix Observatory — {label}")
    print(f"  Location: {lat:.4f}°N, {abs(lon):.4f}°{'W' if lon < 0 else 'E'}")
    print(f"{'='*60}")
    print(f"\nTIER I   SYSTEM : {readiness.system_count} records  {'[WARM]' if readiness.system_ready else '[COLD]'}")
    print(f"TIER II  NATURAL: {readiness.natural_count} records  {'[WARM]' if readiness.natural_ready else '[COLD]'}")
    channels = get_domain_channels()
    print(f"TIER III DOMAIN : {len(channels)} channels configured")
    print(f"\nInstall rich for full helix visualization: pip install rich\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="SignalLogic Helix Dashboard — three-tier signature observatory"
    )
    ap.add_argument("--watch",   action="store_true", help="live refresh every N seconds")
    ap.add_argument("--animate", action="store_true", help="continuously rotating helix animation")
    ap.add_argument("--interval", type=float, default=5.0, help="refresh interval for --watch (default: 5s)")
    ap.add_argument("--fps",     type=float, default=8.0,  help="frames per second for --animate (default: 8)")
    args = ap.parse_args()

    if args.animate:
        run_animate(fps=args.fps)
    elif args.watch:
        run_watch(interval=args.interval)
    else:
        run_snapshot()


if __name__ == "__main__":
    main()
