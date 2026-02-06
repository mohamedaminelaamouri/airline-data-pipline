from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from .data import CsvSource, load_aggregated_csv
from .features import FeatureConfig, FEATURE_COLUMNS_V2, build_training_frame
from .metrics import score_metrics, threshold_metrics
from .split import temporal_split_masks
from .thresholds import choose_cutoff_for_min_missed


@dataclass(frozen=True)
class TrainConfig:
    target_threshold: float = 0.20
    sample_weight: str = "sqrt_flights"  # none|flights|sqrt_flights
    n_estimators: int = 600
    max_depth: int = 5
    learning_rate: float = 0.05
    subsample: float = 0.9
    colsample_bytree: float = 0.9
    reg_lambda: float = 1.0
    random_state: int = 42
    min_recall: float = 0.90


def _sample_weight_from_arr_flights(arr_flights: pd.Series, mode: str) -> np.ndarray | None:
    if mode == "none":
        return None

    flights = pd.to_numeric(arr_flights, errors="coerce").fillna(1.0).clip(lower=1.0)
    if mode == "flights":
        return flights.to_numpy(dtype=float)

    return np.sqrt(flights).to_numpy(dtype=float)


def train_from_csv(*, data_path: str, cfg: TrainConfig) -> dict:
    df_raw = load_aggregated_csv(CsvSource(path=data_path))

    le_airport = LabelEncoder().fit(df_raw["airport"].astype(str))
    le_carrier = LabelEncoder().fit(df_raw["carrier"].astype(str))

    feat_cfg = FeatureConfig(target_threshold=float(cfg.target_threshold))
    X, y = build_training_frame(df_raw, le_carrier=le_carrier, le_airport=le_airport, cfg=feat_cfg)

    train_mask, val_mask, test_mask = temporal_split_masks(
        year=X["year"],
        month=X["month"],
        train_frac=0.70,
        val_frac=0.20,
        test_frac=0.10,
    )

    X_train, y_train = X.loc[train_mask], y.loc[train_mask]
    X_val, y_val = X.loc[val_mask], y.loc[val_mask]
    X_test, y_test = X.loc[test_mask], y.loc[test_mask]

    weights = _sample_weight_from_arr_flights(X_train["arr_flights"], cfg.sample_weight)

    pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                XGBClassifier(
                    n_estimators=int(cfg.n_estimators),
                    max_depth=int(cfg.max_depth),
                    learning_rate=float(cfg.learning_rate),
                    subsample=float(cfg.subsample),
                    colsample_bytree=float(cfg.colsample_bytree),
                    reg_lambda=float(cfg.reg_lambda),
                    random_state=int(cfg.random_state),
                    n_jobs=4,
                    eval_metric="logloss",
                ),
            ),
        ]
    )

    fit_params = {}
    if weights is not None:
        fit_params["model__sample_weight"] = weights

    t0 = time.time()
    pipe.fit(X_train, y_train, **fit_params)
    train_seconds = float(time.time() - t0)

    proba_val = pipe.predict_proba(X_val)[:, 1]
    proba_test = pipe.predict_proba(X_test)[:, 1]

    base_val = score_metrics(y_val.to_numpy(), proba_val)
    base_test = score_metrics(y_test.to_numpy(), proba_test)

    cutoff_policy = choose_cutoff_for_min_missed(
        y_val.to_numpy(),
        proba_val,
        min_recall=float(cfg.min_recall),
    )

    thr = float(cutoff_policy["thr"])
    test_thr = threshold_metrics(y_test.to_numpy(), proba_test, thr)

    return {
        "feature_columns": FEATURE_COLUMNS_V2,
        "model": pipe,
        "encoders": {"carrier": le_carrier, "airport": le_airport},
        "splits": {"train": int(train_mask.sum()), "val": int(val_mask.sum()), "test": int(test_mask.sum())},
        "metrics": {"val": base_val, "test": base_test, "train_seconds": train_seconds},
        "cutoff": {**cutoff_policy, "test_at_cutoff": test_thr.__dict__},
    }


def save_run(*, result: dict, out_dir: str, data_path: str, cfg: TrainConfig) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / "model.pkl"
    le_carrier_path = out / "label_encoder_carrier.pkl"
    le_airport_path = out / "label_encoder_airport.pkl"

    joblib.dump(result["model"], model_path)
    joblib.dump(result["encoders"]["carrier"], le_carrier_path)
    joblib.dump(result["encoders"]["airport"], le_airport_path)

    metrics_out = {
        "run_id": out.name,
        "backend": "sklearn",
        "data": data_path,
        "train_config": cfg.__dict__,
        "splits": result["splits"],
        "metrics": result["metrics"],
        "cutoff": result["cutoff"],
        "artifacts": {"model": str(model_path), "le_carrier": str(le_carrier_path), "le_airport": str(le_airport_path)},
    }

    (out / "metrics.json").write_text(json.dumps(metrics_out, indent=2), encoding="utf-8")
    return out
