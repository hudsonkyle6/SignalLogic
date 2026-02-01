# engine/fix_game_column.py
import pandas as pd
from pathlib import Path

# Path to your main data file
csv_path = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"

df = pd.read_csv(csv_path)

# Label everything as MegaMillions for now
df["Game"] = "MegaMillions"

df.to_csv(csv_path, index=False)
print(f"✅ Updated Game column for {len(df)} rows in {csv_path}")
