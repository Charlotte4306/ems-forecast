"""Read the shared hourly CSV splits without modifying their contents."""
from pathlib import Path

import numpy as np
import pandas as pd

from ems.paths import ROOT
REGRESSORS = [
    "lag_1h", "lag_2h", "lag_3h", "lag_6h", "lag_12h", "lag_24h",
    "lag_48h", "lag_168h", "rolling_mean_24h", "rolling_std_24h",
    "rolling_mean_168h", "rolling_std_168h", "ewm_24h", "ewm_168h",
]


def read_split(data_dir: Path, split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read aligned raw features/target for either model family."""
    X = pd.read_csv(data_dir / f"X_{split}.csv")
    y = pd.read_csv(data_dir / f"y_{split}.csv")
    if len(X) != len(y) or len(X) < 2:
        raise ValueError(f"{split}: X/y must have equal lengths and at least two rows")
    return X, y


def load_split(data_dir: Path, split: str) -> pd.DataFrame:
    """Prepare Prophet's timestamp/target/regressor table."""
    X, y = read_split(data_dir, split)
    calendar = X[["year", "month", "day_of_month", "hour"]].rename(
        columns={"day_of_month": "day"}
    )
    ds = pd.to_datetime(calendar, errors="raise")
    if not ds.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all():
        raise ValueError(f"{split}: timestamps must be unique, sorted and hourly")
    result = X[REGRESSORS].copy()
    result.insert(0, "ds", ds)
    result["y"] = pd.to_numeric(y["call_count"], errors="raise")
    if not np.isfinite(result[["y", *REGRESSORS]].to_numpy()).all():
        raise ValueError(f"{split}: non-finite target or regressors")
    if (result["y"] < 0).any():
        raise ValueError(f"{split}: negative call counts")
    # These lag values were created upstream. Check alignment against actual targets.
    for lag in (1, 2, 3, 6, 12, 24, 48, 168):
        if len(result) > lag and not np.allclose(
            result[f"lag_{lag}h"].iloc[lag:], result["y"].iloc[:-lag]
        ):
            raise ValueError(f"{split}: lag_{lag}h is misaligned with target")
    return result


def load_data(data_dir: Path = ROOT / "data") -> dict[str, pd.DataFrame]:
    splits = {s: load_split(Path(data_dir), s) for s in ("train", "val", "test")}
    for left, right in (("train", "val"), ("val", "test")):
        if splits[right]["ds"].iloc[0] - splits[left]["ds"].iloc[-1] != pd.Timedelta(hours=1):
            raise ValueError(f"{left}/{right}: expected consecutive non-overlapping splits")
    return splits
