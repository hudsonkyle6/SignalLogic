# engine/check_amplitude.py
import pandas as pd
from pathlib import Path

csv_path = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"
df = pd.read_csv(csv_path)

def calc_amp(row):
    nums = [row["N1"], row["N2"], row["N3"], row["N4"], row["N5"]]
    return pd.Series(nums).std()

df["Amplitude"] = df.apply(calc_amp, axis=1)
print(df[["Date", "Amplitude"]].head())
