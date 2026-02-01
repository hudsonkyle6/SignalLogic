# engine_loader.py

import pandas as pd
from pathlib import Path

class DataSchemaError(Exception):
    pass

def load_data(csv_path: Path) -> pd.DataFrame:
    # Load CSV
    df = pd.read_csv(csv_path)

    # Ensure 'Date' column exists or normalize an alias
    if "Date" not in df.columns:
        for alt in ["date", "DrawDate", "draw_date"]:
            if alt in df.columns:
                df.rename(columns={alt: "Date"}, inplace=True)
                break
    if "Date" not in df.columns:
        raise DataSchemaError("No 'Date' column found in the dataset.")

    # ✅ Ensure 'Game' column exists
    if "Game" not in df.columns:
        raise DataSchemaError("No 'Game' column found in the dataset.")

    # Convert date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Normalize column names if needed (optional: lowercase)
    df.columns = [col.strip() for col in df.columns]

    # Attach attribute to help later modules
    df.attrs["number_columns"] = {
        "MegaMillions": ["N1", "N2", "N3", "N4", "N5", "Mega"],
        "Pick5": ["P1", "P2", "P3", "P4", "P5"],
    }

    return df
