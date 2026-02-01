# run_engine.py

from engine_loader import load_data
from engine_rhythm import compute_rhythm
from engine_live_feed import build_or_update
from pathlib import Path
import pandas as pd
import sys

# 👇 Add engine_coupling to the path manually
sys.path.append(str(Path(__file__).parent.parent / "engine coupling"))
from resonance_score import evaluate_signal_state

# === 1. Load and analyze LOTTERY DRAW DATA ===
lottery_path = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"
lottery_df = load_data(lottery_path)
# === 1. Load and analyze LOTTERY DRAW DATA ===
lottery_path = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"
lottery_df = load_data(lottery_path)

# Compute rhythm for each Game type
game_rhythm_dfs = []
all_amplitudes = []

# Define which number columns belong to each game type
game_number_columns = {
    "MegaMillions": ["N1", "N2", "N3", "N4", "N5", "Mega"],
    "Pick5":        ["P1", "P2", "P3", "P4", "P5"]
}

for game, num_cols in game_number_columns.items():
    sub_df = lottery_df[lottery_df["Game"] == game].copy()
    if sub_df.empty:
        continue
    sub_df.attrs = {"number_columns": num_cols}
    summary, sub_df = compute_rhythm(sub_df)
    game_rhythm_dfs.append(sub_df)
    all_amplitudes.append(sub_df["Amplitude"])

# Merge rhythm dataframes
rhythm_df = pd.concat(game_rhythm_dfs).sort_values("Date").reset_index(drop=True)
amplitudes = pd.concat(all_amplitudes).sort_index()

# Compute combined stats
z_score = (amplitudes.iloc[-1] - amplitudes.mean()) / amplitudes.std()
mad = (amplitudes - amplitudes.median()).abs().mean()
z_robust = (amplitudes.iloc[-1] - amplitudes.median()) / (mad + 1e-8)
z_ema = (amplitudes - amplitudes.mean()).ewm(span=5).mean().iloc[-1]
z_mean_window = amplitudes.tail(5).mean()

lottery_stats = {
    'mean': amplitudes.mean(),
    'std': amplitudes.std(),
    'latest': amplitudes.iloc[-1],
    'z_score': z_score,
    'z_robust': z_robust,
    'z_ema': z_ema,
    'z_mean_window': z_mean_window
}


# Get rhythm attributes directly
rhythm_stats = rhythm_df.attrs.get("rhythm", {})

# === 2. Load and update NATURAL RHYTHM DATA ===
lat, lon = 42.9826, -71.8152  # Francestown NH coordinates
natural_df = build_or_update(lat, lon, days_back=14)

# === 3. Load merged signal and compute RESONANCE STATE ===
merged_path = Path(__file__).parent.parent / "data" / "merged_signal.csv"
merged_df = pd.read_csv(merged_path)
# === 3. Load merged signal and compute RESONANCE STATE ===
merged_path = Path(__file__).parent.parent / "data" / "merged_signal.csv"

signal_state = evaluate_signal_state()

# Re-read the merged file to include new columns
merged_df = pd.read_csv(merged_path)
latest = merged_df.iloc[-1]

print("\n📡 Resonance Classification:", latest["SignalState"])

# === 4. Print Signal Rhythm Console ===
latest = merged_df.iloc[-1]

print("\n=== SIGNAL RHYTHM CONSOLE ===")

# 🎲 Lottery draw rhythm
print("\n🎲 Lottery Draw Rhythm:")
print(f"  Mean Amp (8w): {round(rhythm_stats.get('recent_mean_amp', 0), 2)}")
print(f"  Std Dev:       {round(rhythm_stats.get('recent_std_amp', 0), 2)}")
print(f"  Latest Amp:    {round(rhythm_stats.get('latest_amp', 0), 2)}")
print(f"  Z-Score:       {round(rhythm_stats.get('z_score', 0), 2)}")
print(f"  Z-Robust:      {round(rhythm_stats.get('z_robust', 0), 2)}")
print(f"  Z-EMA:         {round(rhythm_stats.get('z_ema', 0), 2)}")
print(f"  Z̄₅ Window:     {round(rhythm_stats.get('z_5', 0), 2)}")

# 📉 Market Rhythm
print("\n📉 Market Rhythm (SP500 + VIX):")
print(f"  SP500 Close:  {round(latest.get('SP500_Close', 0), 2)}")
print(f"  VIX Close:    {round(latest.get('VIX_Close', 0), 2)}")

# 🌒 Natural rhythm
print("\n🌒 Natural Rhythm (Temp + Moon):")
print(natural_df.tail(3).to_string(index=False))

# 📡 Resonance state
print("\n📡 Resonance Classification:", latest['SignalState'])

print("\n==============================")
