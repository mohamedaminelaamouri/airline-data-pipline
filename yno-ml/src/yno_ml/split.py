from __future__ import annotations

import numpy as np
import pandas as pd


def temporal_split_masks(
    *,
    year: pd.Series,
    month: pd.Series,
    train_frac: float = 0.70,
    val_frac: float = 0.20,
    test_frac: float = 0.10,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if not np.isclose(train_frac + val_frac + test_frac, 1.0):
        raise ValueError("train/val/test fractions must sum to 1.0")
    if min(train_frac, val_frac, test_frac) <= 0:
        raise ValueError("train/val/test fractions must be > 0")

    years = pd.to_numeric(year, errors="coerce")
    months = pd.to_numeric(month, errors="coerce")
    period = (years * 12 + months).astype("Int64")
    if period.isna().any():
        raise ValueError("Found NaN in computed period from year/month")

    unique_periods = np.array(sorted(period.unique().tolist()), dtype=int)
    n = unique_periods.size
    if n < 10:
        raise ValueError("Not enough unique periods to do a temporal split")

    train_end_idx = max(1, int(np.floor(train_frac * n)))
    val_end_idx = max(train_end_idx + 1, int(np.floor((train_frac + val_frac) * n)))
    val_end_idx = min(val_end_idx, n - 1)

    train_end_period = unique_periods[train_end_idx - 1]
    val_end_period = unique_periods[val_end_idx - 1]

    train_mask = period <= train_end_period
    val_mask = (period > train_end_period) & (period <= val_end_period)
    test_mask = period > val_end_period

    return train_mask, val_mask, test_mask
