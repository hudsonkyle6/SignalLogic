# engine_rhythm.py
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class Reading:
    mean_amplitude: float
    frequency_per_week: float
    current_phase: str  # "Rising" | "Falling"

def _get_number_cols(df: pd.DataFrame) -> list[str]:
    game_col = df.get("Game", None)
    number_map = df.attrs.get("number_columns", {})

    if game_col is not None and not number_map:
        raise ValueError("No number column mapping found in df.attrs['number_columns'].")

    if game_col is not None and isinstance(number_map, dict):
        unique_games = df["Game"].dropna().unique()
        if len(unique_games) == 1:
            game = unique_games[0]
            return number_map.get(game, [])
        else:
            raise ValueError("Multiple 'Game' types found. Can't determine a single number column set.")

    candidates = [
        ["N1","N2","N3","N4","N5","Mega"],
        ["n1","n2","n3","n4","n5","mega"],
        ["N1","N2","N3","N4","Mega"],
        ["n1","n2","n3","n4","mega"],
    ]
    return next((c for c in candidates if all(x in df.columns for x in c)), None)

def compute_rhythm(df_in: pd.DataFrame) -> tuple[Reading, pd.DataFrame]:
    df = df_in.copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    num_cols = _get_number_cols(df)
    if not num_cols:
        raise ValueError("Could not determine number columns to calculate amplitude.")

    # --- core amplitude computation ---
    df["sum"] = df[num_cols].sum(axis=1, skipna=True)
    df["delta"] = df["sum"].diff()
    df["amp"] = df["delta"].abs()
    df["Amplitude"] = df["amp"]

    # --- rhythm metrics ---
    mean_amp = float(df["amp"].iloc[1:].mean()) if len(df) > 1 else 0.0
    recent_amp = df["amp"].iloc[-8:] if len(df) >= 8 else df["amp"]
    latest_amp = df["amp"].iloc[-1] if len(df) > 0 else 0

    z = (latest_amp - recent_amp.mean()) / (recent_amp.std() + 1e-8)
    mad = (recent_amp - recent_amp.median()).abs().mean()
    z_robust = (latest_amp - recent_amp.median()) / (mad + 1e-8)
    z_ema = (latest_amp - recent_amp.ewm(span=5).mean().iloc[-1]) / (recent_amp.std() + 1e-8)
    z_bar5 = (recent_amp - recent_amp.mean()).mean() / (recent_amp.std() + 1e-8)

    # --- frequency ---
    if len(df) > 1:
        span_days = (df["Date"].max() - df["Date"].min()).days
        weeks = max(1e-9, span_days / 7.0)
        freq = float(len(df) / weeks)
    else:
        freq = 0.0

    # --- phase ---
    if len(df) > 1 and pd.notna(df["delta"].iloc[-1]) and df["delta"].iloc[-1] > 0:
        phase = "Rising"
    else:
        phase = "Falling"

    # --- structured reading ---
    reading = Reading(
        mean_amplitude=mean_amp,
        frequency_per_week=freq,
        current_phase=phase,
    )

    # --- attach rhythm stats for dashboard ---
    df.attrs["rhythm"] = {
        "recent_mean_amp": recent_amp.mean(),
        "recent_std_amp": recent_amp.std(),
        "latest_amp": latest_amp,
        "z_score": z,
        "z_robust": z_robust,
        "z_ema": z_ema,
        "z_5": z_bar5,
    }

    return reading, df

