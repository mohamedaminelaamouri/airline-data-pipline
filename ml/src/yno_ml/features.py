from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureConfig:
    target_threshold: float = 0.20


LEAKAGE_COLUMNS: set[str] = {
    "arr_del15",
    "arr_delay",
    "carrier_delay",
    "weather_delay",
    "nas_delay",
    "security_delay",
    "late_aircraft_delay",
    "carrier_ct",
    "weather_ct",
    "nas_ct",
    "security_ct",
    "late_aircraft_ct",
    "arr_cancelled",
    "arr_diverted",
}


FEATURE_COLUMNS_V2: list[str] = [
    "year",
    "month",
    "month_sin",
    "month_cos",
    "is_summer",
    "is_winter",
    "is_holiday_season",
    "carrier_encoded",
    "airport_encoded",
    "arr_flights",
    "log_arr_flights",
    "pair_lag1",
    "pair_lag3_mean",
    "pair_expanding_mean",
    "airport_lag1",
    "airport_lag3_mean",
    "airport_expanding_mean",
    "carrier_lag1",
    "carrier_lag3_mean",
    "carrier_expanding_mean",
]


def validate_no_leakage(columns: list[str] | set[str]) -> None:
    leaks = sorted(set(columns).intersection(LEAKAGE_COLUMNS))
    if leaks:
        raise ValueError("Data leakage detected in features: " + ", ".join(leaks))


def add_period(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["month"] = pd.to_numeric(out["month"], errors="coerce")
    out["period"] = out["year"].astype("Int64") * 12 + out["month"].astype("Int64")
    return out


def add_delay_rate_and_target(df: pd.DataFrame, cfg: FeatureConfig) -> pd.DataFrame:
    out = df.copy()
    out["arr_flights"] = pd.to_numeric(out.get("arr_flights"), errors="coerce")
    out["arr_del15"] = pd.to_numeric(out.get("arr_del15"), errors="coerce")

    out["delay_rate"] = np.where(
        out["arr_flights"].fillna(0) > 0,
        out["arr_del15"].fillna(0) / out["arr_flights"],
        0.0,
    )

    out["target"] = (out["delay_rate"] > float(cfg.target_threshold)).astype(int)
    return out


def add_seasonality_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    m = pd.to_numeric(out["month"], errors="coerce")
    out["month_sin"] = np.sin(2 * np.pi * m / 12)
    out["month_cos"] = np.cos(2 * np.pi * m / 12)
    out["is_summer"] = m.isin([6, 7, 8]).astype(int)
    out["is_winter"] = m.isin([12, 1, 2]).astype(int)
    out["is_holiday_season"] = m.isin([11, 12]).astype(int)
    return out


def compute_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    out = add_period(df)
    if "delay_rate" not in out.columns:
        out["arr_flights"] = pd.to_numeric(out.get("arr_flights"), errors="coerce")
        out["arr_del15"] = pd.to_numeric(out.get("arr_del15"), errors="coerce")
        out["delay_rate"] = np.where(
            out["arr_flights"].fillna(0) > 0,
            out["arr_del15"].fillna(0) / out["arr_flights"],
            0.0,
        )

    out = out.sort_values(["period", "carrier", "airport"], kind="mergesort")

    def _lags_for(keys: list[str], prefix: str) -> None:
        grp = out.groupby(keys, sort=False)["delay_rate"]
        out[f"{prefix}_lag1"] = grp.shift(1)
        out[f"{prefix}_lag3_mean"] = grp.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        out[f"{prefix}_expanding_mean"] = grp.transform(lambda s: s.shift(1).expanding(min_periods=1).mean())

    _lags_for(["carrier", "airport"], "pair")
    _lags_for(["airport"], "airport")
    _lags_for(["carrier"], "carrier")

    return out


def build_training_frame(
    df_raw: pd.DataFrame,
    *,
    le_carrier,
    le_airport,
    cfg: FeatureConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    df = df_raw.copy()

    df["arr_flights"] = pd.to_numeric(df.get("arr_flights"), errors="coerce")
    df["arr_del15"] = pd.to_numeric(df.get("arr_del15"), errors="coerce")

    df = add_period(df)
    df = add_delay_rate_and_target(df, cfg)
    df = add_seasonality_features(df)

    df["carrier_encoded"] = df["carrier"].apply(lambda x: le_carrier.transform([x])[0] if x in le_carrier.classes_ else 0)
    df["airport_encoded"] = df["airport"].apply(lambda x: le_airport.transform([x])[0] if x in le_airport.classes_ else 0)

    df = compute_lag_features(df)

    df["log_arr_flights"] = np.log1p(df["arr_flights"].clip(lower=0))

    X = df[FEATURE_COLUMNS_V2].copy()
    validate_no_leakage(set(X.columns))
    y = df["target"].copy()

    return X, y


def features_for_request(
    *,
    carrier: str,
    airport: str,
    year: int,
    month: int,
    arr_flights: float | None,
    df_history: pd.DataFrame,
    le_carrier,
    le_airport,
) -> dict[str, Any] | None:
    if carrier not in le_carrier.classes_ or airport not in le_airport.classes_:
        return None

    req_period = int(year) * 12 + int(month)

    hist = df_history.copy()
    hist = add_period(hist)
    hist["arr_flights"] = pd.to_numeric(hist.get("arr_flights"), errors="coerce")
    hist["arr_del15"] = pd.to_numeric(hist.get("arr_del15"), errors="coerce")
    hist["delay_rate"] = hist["arr_del15"] / hist["arr_flights"]

    past = hist[hist["period"] < req_period]
    if past.empty:
        past = hist

    def _safe_last(values: pd.Series) -> float:
        values = values.dropna()
        return float(values.iloc[-1]) if not values.empty else float("nan")

    def _safe_mean_last_n(values: pd.Series, n: int) -> float:
        values = values.dropna()
        return float(values.iloc[-n:].mean()) if not values.empty else float("nan")

    def _stats(frame: pd.DataFrame) -> tuple[float, float, float]:
        if frame.empty:
            return (float("nan"), float("nan"), float("nan"))
        series = frame.sort_values("period")["delay_rate"]
        mean = float(series.dropna().mean()) if not series.dropna().empty else float("nan")
        return (_safe_last(series), _safe_mean_last_n(series, 3), mean)

    pair_frame = past[(past["carrier"] == carrier) & (past["airport"] == airport)]
    airport_frame = past[past["airport"] == airport]
    carrier_frame = past[past["carrier"] == carrier]

    pair_lag1, pair_lag3, pair_mean = _stats(pair_frame)
    airport_lag1, airport_lag3, airport_mean = _stats(airport_frame)
    carrier_lag1, carrier_lag3, carrier_mean = _stats(carrier_frame)

    global_series = past.sort_values("period")["delay_rate"]
    global_mean = float(global_series.dropna().mean()) if not global_series.dropna().empty else 0.2

    def _fill(x: float, default: float) -> float:
        return default if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x)

    pair_lag1 = _fill(pair_lag1, global_mean)
    pair_lag3 = _fill(pair_lag3, global_mean)
    pair_mean = _fill(pair_mean, global_mean)

    airport_lag1 = _fill(airport_lag1, global_mean)
    airport_lag3 = _fill(airport_lag3, global_mean)
    airport_mean = _fill(airport_mean, global_mean)

    carrier_lag1 = _fill(carrier_lag1, global_mean)
    carrier_lag3 = _fill(carrier_lag3, global_mean)
    carrier_mean = _fill(carrier_mean, global_mean)

    if arr_flights is None:
        arr_flights_val = float(past["arr_flights"].median()) if past["arr_flights"].notna().any() else 100.0
    else:
        arr_flights_val = float(arr_flights)

    base = {
        "year": int(year),
        "month": int(month),
        "carrier_encoded": int(le_carrier.transform([carrier])[0]),
        "airport_encoded": int(le_airport.transform([airport])[0]),
        "arr_flights": float(arr_flights_val),
        "log_arr_flights": float(np.log1p(max(arr_flights_val, 0.0))),
        "pair_lag1": pair_lag1,
        "pair_lag3_mean": pair_lag3,
        "pair_expanding_mean": pair_mean,
        "airport_lag1": airport_lag1,
        "airport_lag3_mean": airport_lag3,
        "airport_expanding_mean": airport_mean,
        "carrier_lag1": carrier_lag1,
        "carrier_lag3_mean": carrier_lag3,
        "carrier_expanding_mean": carrier_mean,
    }

    base = add_seasonality_features(pd.DataFrame([base])).iloc[0].to_dict()

    feats = {k: base.get(k) for k in FEATURE_COLUMNS_V2}
    validate_no_leakage(set(feats.keys()))
    return feats
