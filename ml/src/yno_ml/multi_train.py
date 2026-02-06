from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class MultiTrainConfig:
    target_threshold: float = 0.20
    min_recall: float = 0.90
    sample_weight: str = "sqrt_flights"  # none|flights|sqrt_flights


def train_and_save(*, backend: str, data_path: str, out_root: str, cfg: MultiTrainConfig) -> Path:
    """Train using selected backend and write a versioned run directory."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(out_root) / f"{run_id}_{backend}"
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = backend.lower().strip()
    if backend == "sklearn":
        from .train import TrainConfig, save_run, train_from_csv

        train_cfg = TrainConfig(
            target_threshold=cfg.target_threshold,
            min_recall=cfg.min_recall,
            sample_weight=cfg.sample_weight,
        )
        result = train_from_csv(
            data_path=data_path,
            cfg=train_cfg,
        )
        # keep sklearn-compatible artifacts layout
        save_run(result=result, out_dir=str(out_dir), data_path=data_path, cfg=train_cfg)
        return out_dir

    raise ValueError(f"Unknown backend: {backend}. Use sklearn only.")
