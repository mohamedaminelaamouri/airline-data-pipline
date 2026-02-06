from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

import joblib
import pandas as pd

from .data import CsvSource, load_aggregated_csv
from .features import FEATURE_COLUMNS_V2, features_for_request


@dataclass(frozen=True)
class AlertConfig:
    cutoff: float


def latest_run_dir(runs_root: str = "models/runs") -> Path | None:
    root = Path(runs_root)
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None

    # Prefer latest sklearn run (alerting currently supports sklearn artifacts)
    sklearn_candidates: list[Path] = []
    for p in candidates:
        mp = p / "metrics.json"
        if not mp.exists():
            continue
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(meta.get("backend", "")).lower() == "sklearn":
            sklearn_candidates.append(p)

    if sklearn_candidates:
        return sorted(sklearn_candidates, key=lambda p: p.name)[-1]

    # Fallback to latest directory if no metadata exists
    return sorted(candidates, key=lambda p: p.name)[-1]


def load_artifacts_from_run(run_dir: Path) -> tuple[object, object, object]:
    mp = run_dir / "metrics.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
            backend = str(meta.get("backend", "sklearn")).lower()
            if backend != "sklearn":
                raise RuntimeError(
                    f"Alerting currently supports sklearn runs only. Got backend={backend}. "
                    "Train with --backend sklearn, or pass a sklearn run dir."
                )
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise

    model_path = run_dir / "model.pkl"
    le_carrier_path = run_dir / "label_encoder_carrier.pkl"
    le_airport_path = run_dir / "label_encoder_airport.pkl"
    return (joblib.load(model_path), joblib.load(le_carrier_path), joblib.load(le_airport_path))


def score_month_to_csv(
    *,
    year: int,
    month: int,
    cutoff: float,
    history_csv: str,
    run_dir: Path | None,
    out_csv: str,
) -> Path:
    if run_dir is None:
        run_dir = latest_run_dir()
    if run_dir is None:
        raise RuntimeError("No trained run found under models/runs. Train first.")

    model, le_carrier, le_airport = load_artifacts_from_run(run_dir)

    df_hist = load_aggregated_csv(CsvSource(path=history_csv))

    # IMPORTANT: do NOT score the cartesian product (carriers x airports).
    # It can be extremely large and slow. Score only pairs observed in history.
    pairs = (
        df_hist[["carrier", "airport"]]
        .astype(str)
        .dropna()
        .drop_duplicates()
        .sort_values(["carrier", "airport"], ascending=True)
        .reset_index(drop=True)
    )

    rows: list[dict] = []
    total = int(len(pairs))
    for i, row in pairs.iterrows():
        carrier = str(row["carrier"])
        airport = str(row["airport"])
        feats = features_for_request(
            carrier=carrier,
            airport=airport,
            year=int(year),
            month=int(month),
            arr_flights=None,
            df_history=df_hist,
            le_carrier=le_carrier,
            le_airport=le_airport,
        )
        if not feats:
            continue

        X = pd.DataFrame([feats]).reindex(columns=FEATURE_COLUMNS_V2)
        proba = float(model.predict_proba(X)[0, 1])
        rows.append(
            {
                "carrier": carrier,
                "airport": airport,
                "year": int(year),
                "month": int(month),
                "probability": proba,
                "prediction": int(proba > float(cutoff)),
            }
        )

        # Lightweight progress every ~5%
        if total > 0 and (i % max(1, total // 20) == 0):
            print(f"Scoring progress: {i}/{total}")

    out_df = pd.DataFrame(rows)
    if out_df.empty:
        raise RuntimeError("No rows scored. Check history data and encoders.")

    out_df["risk_score"] = (out_df["probability"] * 100.0).round(2)
    out_df["cutoff"] = float(cutoff)
    out_df["run_id"] = run_dir.name
    out_df["timestamp"] = datetime.now().isoformat()

    out_df = out_df.sort_values(["prediction", "probability"], ascending=[False, False])

    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    return out_path
