from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .multi_train import MultiTrainConfig, train_and_save


@dataclass(frozen=True)
class CompareConfig:
    data_path: str
    out_root: str = "models/runs"
    out_csv: str = "reports/backend_comparison.csv"
    backends: tuple[str, ...] = ("sklearn",)
    train_cfg: MultiTrainConfig = MultiTrainConfig()


def compare_backends(cfg: CompareConfig) -> Path:
    rows: list[dict[str, Any]] = []

    for backend in cfg.backends:
        try:
            run_dir = train_and_save(
                backend=backend,
                data_path=cfg.data_path,
                out_root=cfg.out_root,
                cfg=cfg.train_cfg,
            )
            metrics_path = run_dir / "metrics.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}

            rows.append(
                {
                    "backend": backend,
                    "run_id": metrics.get("run_id", run_dir.name),
                    "train_seconds": (metrics.get("metrics", {}) or {}).get("train_seconds"),
                    "val_roc_auc": (metrics.get("metrics", {}) or {}).get("val", {}).get("roc_auc"),
                    "val_pr_auc": (metrics.get("metrics", {}) or {}).get("val", {}).get("pr_auc"),
                    "test_roc_auc": (metrics.get("metrics", {}) or {}).get("test", {}).get("roc_auc"),
                    "test_pr_auc": (metrics.get("metrics", {}) or {}).get("test", {}).get("pr_auc"),
                    "recommended_cutoff": (metrics.get("cutoff", {}) or {}).get("thr"),
                }
            )
        except Exception as e:
            rows.append({"backend": backend, "error": str(e)})

    out_path = Path(cfg.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return out_path
