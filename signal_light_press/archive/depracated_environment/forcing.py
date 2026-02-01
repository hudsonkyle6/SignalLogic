# -------------------------------------------------------------
#  ENVIRONMENT FORCING ENGINE (Final V1.2 — Fully Stabilized)
# -------------------------------------------------------------
import os
import pandas as pd
import numpy as np

# -------------------------------------------------------------
# 1. True ROOT — corrected path (4 levels up)
# -------------------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA = os.path.join(ROOT, "data")

ENV_PATH = os.path.join(DATA, "environment", "environment_rhythm.csv")
MERGED_PATH = os.path.join(DATA, "merged", "merged_signal.csv")


# -------------------------------------------------------------
# 2. Weather Volatility Index
# -------------------------------------------------------------
def compute_wvi(df_env):
    df = df_env.copy()

    for col in ["temp", "pressure", "wind"]:
        df[col + "_vol"] = df[col].pct_change().abs().fillna(0)

    df["temp_norm"] = df["temp_vol"] / (df["temp_vol"].max() + 1e-9)
    df["pressure_norm"] = df["pressure_vol"] / (df["pressure_vol"].max() + 1e-9)
    df["wind_norm"] = df["wind_vol"] / (df["wind_vol"].max() + 1e-9)

    df["WVI"] = (
        0.4 * df["temp_norm"] +
        0.35 * df["pressure_norm"] +
        0.25 * df["wind_norm"]
    )

    return df[["Date", "WVI"]]


# -------------------------------------------------------------
# 3. Forcing Engine
# -------------------------------------------------------------
def apply_environment_forcing():
    print("[FORCING] Environment forcing engine started.")

    # ---- Path validation ----
    if not os.path.exists(MERGED_PATH):
        print(f"[FORCING] ❌ merged_signal.csv missing:\n        {MERGED_PATH}")
        print("          → Run kernel first.")
        return

    if not os.path.exists(ENV_PATH):
        print(f"[FORCING] ❌ environment_rhythm.csv missing:\n        {ENV_PATH}")
        print("          → Run environment fetch first.")
        return

    # ---- Load datasets ----
    merged = pd.read_csv(MERGED_PATH)
    env = pd.read_csv(ENV_PATH)

    print("[FORCING] Computing Weather Volatility Index (WVI)...")
    wvi_df = compute_wvi(env)

    merged["Date"] = pd.to_datetime(merged["Date"]).dt.date
    wvi_df["Date"] = pd.to_datetime(wvi_df["Date"]).dt.date

    # ---- Merge WVI ----
    merged = merged.merge(wvi_df, on="Date", how="left")
    # Ensure WVI column exists BEFORE we try to fill it
    if "WVI" not in merged.columns:
        merged["WVI"] = 0.0
    else:
        merged["WVI"] = merged["WVI"].fillna(0)


    # ---- Ensure EnvPressure column exists ----
    if "EnvPressure" not in merged.columns:
        merged["EnvPressure"] = 0.5  # neutral baseline

    # ---- Compute EnvFactor ----
    merged["EnvFactor"] = (
        0.7 * merged["EnvPressure"] +
        0.3 * merged["WVI"]
    )

    # ---- Save ----
    merged.to_csv(MERGED_PATH, index=False)
    print(f"[FORCING] ✅ WVI + EnvFactor injected → {MERGED_PATH}")


# -------------------------------------------------------------
# 4. Main
# -------------------------------------------------------------
if __name__ == "__main__":
    apply_environment_forcing()

