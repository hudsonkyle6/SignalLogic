from __future__ import annotations

import pandas as pd
from pathlib import Path

from rhythm_os.oracle.validate import validate_oracle_inputs, OracleContractError


def main():
    merged_path = Path("data/merged/merged_signal.csv")
    print("🔍 Oracle Contract v1 — DRY RUN")
    print(f"Loading: {merged_path.resolve()}")

    df = pd.read_csv(merged_path)

    try:
        validate_oracle_inputs(df, ctx="ORACLE_DRY_RUN", layer="L1")
        print("✅ Oracle Contract v1 PASSED (today row)")
    except OracleContractError as e:
        print("❌ Oracle Contract v1 FAILED")
        print("Reason:")
        print(e)


if __name__ == "__main__":
    main()
