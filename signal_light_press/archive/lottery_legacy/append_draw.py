import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

DATA_PATH = Path(__file__).parent.parent / "data" / "mega_millions_longterm.csv"

# --- CONFIG ---
MEGA_MAIN_MIN, MEGA_MAIN_MAX = 1, 70
MEGA_MEGA_MIN, MEGA_MEGA_MAX = 1, 25

PICK_MIN, PICK_MAX = 1, 39
# ---------------

def ensure_df():
    """Ensure the CSV exists and has the full unified schema."""
    cols = [
        "Date", "N1", "N2", "N3", "N4", "N5", "Mega",
        "P1", "P2", "P3", "P4", "P5", "Game", "Amplitude"
    ]
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
        # add any missing columns
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
    else:
        df = pd.DataFrame(columns=cols)
    return df


def validate_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be YYYY-MM-DD (e.g., 2025-11-05)")


def append_megamillions(df: pd.DataFrame, date_obj, n1, n2, n3, n4, n5, mega):
    new_row = {
        "Date": date_obj,
        "N1": n1, "N2": n2, "N3": n3, "N4": n4, "N5": n5, "Mega": mega,
        "P1": np.nan, "P2": np.nan, "P3": np.nan, "P4": np.nan, "P5": np.nan,
        "Game": "MegaMillions",
        "Amplitude": np.nan,
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


def append_pick5(df: pd.DataFrame, date_obj, p1, p2, p3, p4, p5):
    new_row = {
        "Date": date_obj,
        "N1": np.nan, "N2": np.nan, "N3": np.nan, "N4": np.nan, "N5": np.nan, "Mega": np.nan,
        "P1": p1, "P2": p2, "P3": p3, "P4": p4, "P5": p5,
        "Game": "Pick5",
        "Amplitude": np.nan,
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


def save(df):
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    df.to_csv(DATA_PATH, index=False)
    print(f"💾 Saved → {DATA_PATH}")


def interactive_loop():
    df = ensure_df()
    while True:
        game = input("Enter game type (MegaMillions or Pick5): ").strip()
        date_str = input("Enter draw date (YYYY-MM-DD): ").strip()
        date_obj = validate_date(date_str)

        if game.lower() == "megamillions":
            nums = [int(input(f"N{i}: ")) for i in range(1, 6)]
            mega = int(input("Mega number: "))
            df = append_megamillions(df, date_obj, *nums, mega)
            print(f"✅ Added MegaMillions draw {date_str} → {nums}, Mega:{mega}")

        elif game.lower() == "pick5":
            picks = [int(input(f"P{i}: ")) for i in range(1, 6)]
            df = append_pick5(df, date_obj, *picks)
            print(f"✅ Added Pick5 draw {date_str} → {picks}")

        else:
            print("⚠️ Invalid game type. Choose MegaMillions or Pick5.")
            continue

        save(df)
        if input("Add another? (y/n): ").lower() != "y":
            break


def cli_mode(args):
    df = ensure_df()
    date_obj = validate_date(args.date)
    if args.game.lower() == "megamillions":
        df = append_megamillions(df, date_obj, args.n1, args.n2, args.n3, args.n4, args.n5, args.mega)
        print(f"✅ Added MegaMillions draw {date_obj.date()}")
    elif args.game.lower() == "pick5":
        df = append_pick5(df, date_obj, args.p1, args.p2, args.p3, args.p4, args.p5)
        print(f"✅ Added Pick5 draw {date_obj.date()}")
    else:
        raise ValueError("Invalid game type. Use --game MegaMillions or --game Pick5.")
    save(df)


def parse_args():
    p = argparse.ArgumentParser(description="Append a new draw to the long-term dataset")
    p.add_argument("--game", type=str, help="MegaMillions or Pick5")
    p.add_argument("--date", type=str)
    # MegaMillions numbers
    p.add_argument("--n1", type=int)
    p.add_argument("--n2", type=int)
    p.add_argument("--n3", type=int)
    p.add_argument("--n4", type=int)
    p.add_argument("--n5", type=int)
    p.add_argument("--mega", type=int)
    # Pick5 numbers
    p.add_argument("--p1", type=int)
    p.add_argument("--p2", type=int)
    p.add_argument("--p3", type=int)
    p.add_argument("--p4", type=int)
    p.add_argument("--p5", type=int)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.game:
        cli_mode(args)
    else:
        interactive_loop()

