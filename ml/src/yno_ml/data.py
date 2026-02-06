from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .schema import validate_required_columns


@dataclass(frozen=True)
class CsvSource:
    path: str


def load_aggregated_csv(source: CsvSource) -> pd.DataFrame:
    df = pd.read_csv(source.path)
    validate_required_columns(df.columns.tolist())
    return df
