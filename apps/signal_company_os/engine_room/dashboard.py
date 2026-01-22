# rhythm_os/core/dashboard.py
"""
Rhythm OS — Dashboard Renderer V3.31
Stable, safe, clean amplitude + full NAT / MARKET context.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, date

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]  # -> SignalLogic/
DATA_DIR = ROOT / "data"
MERGED_PATH = DATA_DIR / "merged" / "merged_signal.csv"


# ---------------------------------------------------------
# Sparkline
# ---------------------------------------------------------
def sparkline(values, width: int = 28) -> str:
    clean = [v for v in values if pd.notna(v)]
    if not clean:
        return " " * width

    blocks = "▁▂▃▄▅▆▇█"
    mn, mx = min(clean), max(clean)
    if mx == mn:
        return blocks[0] * min(len(clean), width)

    out = []
    for v in clean:
        n = (v - mn) / (mx - mn)
        idx = int(max(0, min(n * (len(blocks) - 1), len(blocks) - 1)))
        out.append(blocks[idx])

    if len(out) > width:
        out = out[-width:]

    return "".join(out)


# ---------------------------------------------------------
# Bar for resonance
# ---------------------------------------------------------
def _bar(value: float, width: int = 30) -> str:
    try:
        v = float(value)
    except Exception:
        v = 0.0

    midpoint = width // 2
    pos = int((v + 1) / 2 * width)
    pos = max(0, min(pos, width))

    out = ""
    for i in range(width):
        if i == midpoint:
            out += "|"
        elif i < pos:
            out += "█"
        else:
            out += " "
    return out


# ---------------------------------------------------------
# Narrative
# ---------------------------------------------------------
def _narrative(state: str, season: str) -> str:
    if "Resonant" in state:
        return {
            "Build":   "Spring rises — the pattern clears.",
            "Fuel":    "Summer hums at full momentum.",
            "Tend":    "Autumn sharpens the frame.",
            "Reflect": "Winter resonates in stillness.",
        }.get(season, "Energy gathers cleanly.")

    if "Still" in state:
        return "The system holds its breath; a quiet neutrality prevails."

    if "Turbulent" in state:
        return "Crosscurrents stir beneath the surface; proceed with awareness."

    return "The rhythm is faint today — listen closely."


def _safe_date(raw) -> str:
    if pd.isna(raw):
        return "unknown"
    if isinstance(raw, (datetime, date)):
        return raw.strftime("%Y-%m-%d")
    if hasattr(raw, "strftime"):
        try:
            return raw.strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(raw)
    if s.lower() == "nat":
        return "unknown"
    return s[:10]


def _arrow(delta: float) -> str:
    try:
        if pd.isna(delta):
            return "→ 0.00"
        d = float(delta)
        if d > 0:
            return f"▲ +{d:.2f}"
        if d < 0:
            return f"▼ {d:.2f}"
        return "→ 0.00"
    except Exception:
        return "→ 0.00"


# ---------------------------------------------------------
# Render Dashboard
# ---------------------------------------------------------
def render_dashboard(latest) -> None:
    """
    Accepts:
        • dict
        • Series
        • DataFrame (takes last row)
    Fully safe — no .iloc on strings or malformed input.
    """

    # ---- SAFEST NORMALIZATION LOGIC (PATCHED) ----
    if isinstance(latest, dict):
        pass
    elif hasattr(latest, "to_dict"):   # Series
        latest = latest.to_dict()
    elif hasattr(latest, "iloc"):      # DataFrame
        latest = latest.iloc[-1].to_dict()
    else:
        latest = {"Date": str(latest)}  # fallback

    # ----------------------------------------------------
    # Extract fields
    # ----------------------------------------------------
    date_str = _safe_date(latest.get("Date"))
    season = latest.get("Season", "?")
    state = latest.get("SignalState", "?")

    try:
        res = float(latest.get("ResonanceValue", 0.0))
    except Exception:
        res = 0.0

    amp_today = latest.get("Amplitude", "?")

    sp = latest.get("SP500Close", latest.get("SP500_Close", "nan"))
    vx = latest.get("VIXClose", latest.get("VIX_Close", "nan"))
    temp = latest.get("TempAvg", "nan")
    moon = latest.get("MoonIllum", "nan")

    # ----------------------------------------------------
    # Load merged for sparkline
    # ----------------------------------------------------
    if MERGED_PATH.exists():
        try:
            df = pd.read_csv(MERGED_PATH)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    if "Amplitude" in df.columns and not df.empty:
        amps = df["Amplitude"].tail(25).to_list()
        spark = sparkline(amps)

        if len(df) >= 2:
            try:
                delta_amp = float(df["Amplitude"].iloc[-1]) - float(df["Amplitude"].iloc[-2])
            except Exception:
                delta_amp = 0.0
        else:
            delta_amp = 0.0

        amp_7 = float(df["Amplitude"].tail(7).mean()) if len(df) >= 7 else 0.0
        amp_21 = float(df["Amplitude"].tail(21).mean()) if len(df) >= 21 else 0.0
    else:
        spark = ""
        delta_amp = 0.0
        amp_7 = 0.0
        amp_21 = 0.0

    try:
        moon_str = f"{float(moon):.2f}"
    except Exception:
        moon_str = str(moon)

    # ----------------------------------------------------
    # PRINT DASHBOARD
    # ----------------------------------------------------
    print("\n" + "═" * 60)
    print("                 📡 SIGNAL ENGINE — DASHBOARD V3.31")
    print("═" * 60)
    print(f"  Date:       {date_str}")
    print(f"  Season:     {season}")
    print(f"  State:      {state}")
    print(f"  Resonance:  {res:.2f}")
    print(f"  {_bar(res)}")

    print("─" * 60)
    print("  TREND")
    print(f"    • Amplitude Sparkline (25d):  {spark}")
    print(f"    • Δ Amplitude Today:          {_arrow(delta_amp)}")
    print(f"    • 7-Day Avg:                  {amp_7:.2f}")
    print(f"    • 21-Day Avg:                 {amp_21:.2f}")

    print("─" * 60)
    print("  MARKET")
    print(f"    • S&P 500 Close:  {sp}")
    print(f"    • VIX Close:      {vx}")

    print("─" * 60)
    print("  NATURAL")
    print(f"    • TempAvg:        {temp}°C")
    print(f"    • MoonIllum:      {moon_str}")

    print("─" * 60)
    print("  AMPLITUDE")
    print(f"    • Amplitude:      {amp_today}")

    print("─" * 60)
    print("  NARRATIVE")
    print(f"    {_narrative(state, season)}")
    print("═" * 60 + "\n")
