from __future__ import annotations

import numpy as np

from .metrics import threshold_metrics


def choose_cutoff_for_min_missed(
    y_val: np.ndarray,
    proba_val: np.ndarray,
    *,
    min_recall: float = 0.90,
    grid: np.ndarray | None = None,
) -> dict:
    """Pick a cutoff that prioritizes recall on validation.

    Strategy:
    - choose the highest cutoff that still satisfies recall >= min_recall
      (higher cutoff => fewer alerts while keeping recall constraint)
    - fallback: maximize recall if nothing is feasible
    """

    if grid is None:
        grid = np.linspace(0.01, 0.60, 60)

    rows = [threshold_metrics(y_val, proba_val, float(t)) for t in grid]

    feasible = [r for r in rows if r.rec1 >= float(min_recall)]
    if feasible:
        best = max(feasible, key=lambda r: r.thr)
        return {"policy": "min_missed_with_recall_constraint", "min_recall": float(min_recall), **best.__dict__}

    best = max(rows, key=lambda r: r.rec1)
    return {"policy": "fallback_max_recall", "min_recall": float(min_recall), **best.__dict__}
