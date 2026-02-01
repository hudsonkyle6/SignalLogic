#engine_core.py
import pandas as pd
from pathlib import Path
from datetime import datetime
import numpy as np
import os
import sys
from colorama import init as color_init, Fore, Style
color_init()

###

def load_data():
    data_path = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"
    df = pd.read_csv(data_path, parse_dates=["Date"])
    return df

def compute_rhythm(df: pd.DataFrame):
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    # Sum for MegaMillions and Pick 5 (if columns exist)
    mm_cols = ["N1", "N2", "N3", "N4", "N5", "Mega"]
    p5_cols = ["P1", "P2", "P3", "P4", "P5"]

    df["mm_sum"] = df[mm_cols].sum(axis=1, min_count=1) if all(c in df.columns for c in mm_cols) else np.nan
    df["p5_sum"] = df[p5_cols].sum(axis=1, min_count=1) if all(c in df.columns for c in p5_cols) else np.nan

    # Use both if available, or fallback
    df["sum"] = df[["mm_sum", "p5_sum"]].mean(axis=1, skipna=True)
    df["delta"] = df["sum"].diff()

    # Signal statistics
    mean_amp = df["delta"].abs().mean() if len(df) > 1 else 0.0
    weeks = (df["Date"].max() - df["Date"].min()).days / 7 if len(df) > 1 else 1
    freq = len(df) / weeks if weeks > 0 else 0.0
    phase = "Rising" if (len(df) > 1 and df["delta"].iloc[-1] > 0) else "Falling"

    reading = {
        "mean_amplitude": float(mean_amp) if pd.notna(mean_amp) else 0.0,
        "frequency_per_week": float(freq) if pd.notna(freq) else 0.0,
        "current_phase": phase,
    }
    return reading, df

###
def compute_baseline(df, window_days=56, window_count=30, alpha=0.25):
   

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    # Detect number columns (4 or 5 main balls, any case)
    candidates = [
        ["N1","N2","N3","N4","N5","Mega"],
        ["N1","N2","N3","N4","Mega"],
        ["n1","n2","n3","n4","n5","mega"],
        ["n1","n2","n3","n4","mega"],
    ]
    nums = next((cols for cols in candidates if all(c in df.columns for c in cols)), None)
    if not nums:
        return {"recent_mean_amp": float("nan"), "recent_std_amp": float("nan"),
                "latest_amp": float("nan"), "z_score": 0.0,
                "z_roll": 0.0, "z_tail": [], "z_robust": 0.0, "z_ema": 0.0}

    for c in nums:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "delta" not in df.columns:
        df["sum"] = df[nums].sum(axis=1)
        df["delta"] = df["sum"].diff()

    if len(df) < 2:
        return {"recent_mean_amp": float("nan"), "recent_std_amp": float("nan"),
                "latest_amp": float("nan"), "z_score": 0.0,
                "z_roll": 0.0, "z_tail": [], "z_robust": 0.0, "z_ema": 0.0}

    # Window: prefer last N draws for a tighter, consistent comparison
    if window_count and window_count > 1:
        recent = df.tail(window_count).copy()
    else:
        cutoff = df["Date"].max() - pd.Timedelta(days=window_days)
        recent = df[df["Date"] >= cutoff].copy() or df.copy()

    # Amplitudes
    recent["amp"] = recent["delta"].abs()
    latest_amp = float(df["delta"].abs().iloc[-1])

    # Classic z (mean/std)
    mean_ = float(recent["amp"].mean())
    std_  = float(recent["amp"].std(ddof=1)) if len(recent) > 1 else 0.0
    z = (latest_amp - mean_) / std_ if std_ > 0 else 0.0

    # Robust z (median/MAD -> sigma-equivalent)
    med = float(np.median(recent["amp"]))
    mad = float(np.median(np.abs(recent["amp"] - med)))
    sigma_eq = 1.4826 * mad
    z_robust = (latest_amp - med) / sigma_eq if sigma_eq > 0 else 0.0

    # EMA baseline z (reacts quicker to recent changes)
    ema = recent["amp"].ewm(alpha=alpha, adjust=False).mean().iloc[-1]
    ema_std = np.sqrt(recent["amp"].ewm(alpha=alpha, adjust=False).var().iloc[-1]) if len(recent) > 1 else 0.0
    z_ema = (latest_amp - float(ema)) / float(ema_std) if ema_std and ema_std > 0 else 0.0

    # z series for breathing strip
    if std_ > 0:
        z_series = (df["delta"].abs() - mean_) / std_
    else:
        z_series = pd.Series(0.0, index=df.index)
    z_roll_series = z_series.rolling(window=5, min_periods=1).mean()
    z_tail = z_roll_series.tail(25).tolist()

    return {
        "recent_mean_amp": mean_,
        "recent_std_amp": std_,
        "latest_amp": latest_amp,
        "z_score": z,          # classic
        "z_robust": z_robust,  # robust median/MAD
        "z_ema": z_ema,        # EMA-based
        "z_roll": float(z_roll_series.iloc[-1]),
        "z_tail": z_tail,
    }


# Simple ASCII meter for the console
def _bar(value, max_val, width=30, fill="█", empty="·"):
    try:
        if max_val is None or max_val <= 0:
            filled = 0
        else:
            ratio = max(0.0, min(1.0, float(value) / float(max_val)))
            filled = int(round(ratio * width))
    except Exception:
        filled = 0
    return fill * filled + empty * (width - filled)

def _bar(value, max_val, width=30, fill="█", empty="·"):
    try:
        if max_val is None or max_val <= 0:
            filled = 0
        else:
            ratio = max(0.0, min(1.0, float(value) / float(max_val)))
            filled = int(round(ratio * width))
    except Exception:
        filled = 0
    return fill * filled + empty * (width - filled)

def _spark(values, width=25):
    # mini sparkline from a list of recent values
    try:
        import pandas as pd
        chars = "▁▂▃▄▅▆▇█"
        if not values:
            return "·" * width
        ser = pd.Series(values[-width:])
        if ser.std() == 0 or ser.isna().all():
            return "·" * min(width, len(values))
        scaled = (ser - ser.min()) / (ser.max() - ser.min())
        idxs = (scaled * (len(chars) - 1)).astype(int)
        return "".join(chars[i] for i in idxs)
    except Exception:
        return "·" * width

def render_console(reading, base):
    """
    Pretty console block for the Forge.
    reading = {"mean_amplitude", "frequency_per_week", "current_phase"}
    base    = {"recent_mean_amp", "recent_std_amp", "latest_amp", "z_score", "z_roll", "z_tail"}
    """
    amp   = reading["mean_amplitude"]
    freq  = reading["frequency_per_week"]
    phase = reading["current_phase"]
    z     = base["z_score"]

    # choose a max for meter (adaptive: 3σ band if available, else 100)
    max_for_meter = 3 * base["recent_std_amp"] + (base["recent_mean_amp"] or 0)
    if not max_for_meter or max_for_meter <= 0 or not (max_for_meter == max_for_meter):
        max_for_meter = max(100.0, amp * 1.5)

    # colors
    if z >= 2:
        c = Fore.RED;   advisory = "High volatility spike (≥2σ)."
    elif z <= -2:
        c = Fore.CYAN;  advisory = "Unusually calm (≤-2σ)."
    else:
        c = Fore.GREEN; advisory = "Within normal range."

    arrow = "↘" if phase.lower().startswith("f") else "↗"

    print("")
    print(Style.BRIGHT + "=== SIGNAL LOGIC :: FORGE READOUT ===" + Style.RESET_ALL)
    print(f"{Fore.YELLOW}Phase{Style.RESET_ALL}: {phase} {arrow}")
    print(f"{Fore.YELLOW}Amplitude{Style.RESET_ALL}: {amp:6.2f}  [{_bar(amp, max_for_meter)}]")
    print(f"{Fore.YELLOW}Frequency{Style.RESET_ALL}: {freq:4.2f} / week")
    print(
        f"{Fore.YELLOW}Baseline{Style.RESET_ALL}: "
        f"mean(30)={base['recent_mean_amp']:.2f}  "
        f"σ={base['recent_std_amp']:.2f}  "
        f"latest_amp={base['latest_amp']:.2f}  "
        f"z={base['z_score']:+.2f}  "
        f"z_robust={base['z_robust']:+.2f}  "
        f"z_ema={base['z_ema']:+.2f}  "
        f"z̄₅={base['z_roll']:+.2f}"
    )
    print(f"{Fore.MAGENTA}Breathing{Style.RESET_ALL}: {_spark(base.get('z_tail', []))}")
    print(f"{c}Advisory{Style.RESET_ALL}: {advisory}")
    print("======================================")

def write_fieldnote(reading, base=None):
    note_path = Path(__file__).parent.parent / "fieldnotes"
    note_path.mkdir(exist_ok=True)
    filename = note_path / f"reading_{datetime.now().date()}.txt"
    ztxt = f", Z:{base['z_score']:.2f}" if base else ""
    with open(filename, "a") as f:
        f.write(
            f"{datetime.now().isoformat()} | "
            f"Amp:{reading['mean_amplitude']:.2f}, "
            f"Freq:{reading['frequency_per_week']:.2f}, "
            f"Phase:{reading['current_phase']}{ztxt}\n"
        )


    print(f"Fieldnote saved → {filename}")
