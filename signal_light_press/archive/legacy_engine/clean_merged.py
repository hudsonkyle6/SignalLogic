import pandas as pd
from pathlib import Path

path = Path("C:/Users/SignalADmin/Signal Archive/SignalLogic/data/merged_signal.csv")

df = pd.read_csv(path)

# remove any rows where Date is NaN
df = df[df["Date"].notna()]

df.to_csv(path, index=False)
print("Cleaned merged_signal.csv — NaN rows removed.")
