from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

NAT_PATH = Path(__file__).parent.parent / "data" / "natural_rhythm.csv"

@dataclass(frozen=True)
class CouplingStat:
    col: str
    lag_days: int
    n: int
    pearson: float
    spearman: float
    note: str = ""

def couple_by_date(rhythm_df: pd.DataFrame,
                   nat_path: Path = NAT_PATH,
                   tolerance_hrs: int = 36) -> pd.DataFrame:

    if not nat_path.exists():
        raise FileNotFoundError(f"Natural rhythm file not found: {nat_path}")

    nat = pd.read_csv(nat_path, parse_dates=["Date"])
    nat = nat.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    df = rhythm_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # Support V2: if no 'amp', but 'Amplitude' exists, alias it
    if "amp" not in df.columns:
        if "Amplitude" in df.columns:
            df["amp"] = df["Amplitude"]
        elif "delta" in df.columns:
            df["amp"] = df["delta"].abs()
        else:
            raise ValueError("couple_by_date expects 'amp', 'Amplitude', or 'delta'")

    merged = pd.merge_asof(
        df, nat,
        on="Date", direction="nearest",
        tolerance=pd.Timedelta(hours=tolerance_hrs)
    )
    return merged

def _corr_pair(x: pd.Series, y: pd.Series) -> Tuple[float, float, int]:
    s = pd.DataFrame({"x": x, "y": y}).dropna()
    n = len(s)
    if n < 12:
        return (float("nan"), float("nan"), n)
    pear = float(s["x"].corr(s["y"], method="pearson"))
    spear = float(s["x"].corr(s["y"], method="spearman"))
    return (pear, spear, n)

def scan_lags(merged: pd.DataFrame,
              nat_col: str,
              max_lag_days: int = 7) -> CouplingStat:

    # Determine amplitude column (legacy 'amp' or V2 'Amplitude')
    amp_col = "amp" if "amp" in merged.columns else "Amplitude"

    base = merged[["Date", amp_col, nat_col]].dropna()
    if len(base) < 20:
        return CouplingStat(col=nat_col, lag_days=0, n=len(base),
                            pearson=float("nan"), spearman=float("nan"),
                            note="insufficient data")

    best = CouplingStat(col=nat_col, lag_days=0, n=0, pearson=-2.0, spearman=float("nan"))

    for lag in range(0, max_lag_days + 1):
        tmp = base.copy()
        tmp[nat_col] = tmp[nat_col].shift(lag)
        pear, spear, n = _corr_pair(tmp[amp_col], tmp[nat_col])
        if np.isnan(pear):
            continue
        if abs(pear) > abs(best.pearson):
            best = CouplingStat(col=nat_col, lag_days=lag, n=n, pearson=pear, spearman=spear)
    return best

def summarize_coupling(merged: pd.DataFrame,
                       cols: Optional[List[str]] = None,
                       max_lag_days: int = 7) -> Dict[str, CouplingStat]:

    if cols is None:
        candidates = ["MoonIllum", "MoonAge", "TempAvg", "TideMean"]
        cols = [c for c in candidates if c in merged.columns]

    out: Dict[str, CouplingStat] = {}
    for c in cols:
        out[c] = scan_lags(merged, c, max_lag_days=max_lag_days)
    return out

def best_signal(couplings: Dict[str, CouplingStat]) -> Optional[CouplingStat]:
    valid = [v for v in couplings.values() if not np.isnan(v.pearson)]
    if not valid:
        return None
    return max(valid, key=lambda v: abs(v.pearson))
