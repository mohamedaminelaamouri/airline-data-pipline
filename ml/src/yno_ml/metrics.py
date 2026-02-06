from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_fscore_support


@dataclass(frozen=True)
class ThresholdMetrics:
    thr: float
    alert_rate: float
    prec1: float
    rec1: float
    f1_1: float
    bal_acc: float


def threshold_metrics(y_true: np.ndarray, proba: np.ndarray, thr: float) -> ThresholdMetrics:
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba).astype(float)

    pred = (proba > float(thr)).astype(int)

    p1, r1, f1, _ = precision_recall_fscore_support(
        y_true, pred, pos_label=1, average="binary", zero_division=0
    )

    # class-0 recall
    _, r0, _, _ = precision_recall_fscore_support(
        1 - y_true, 1 - pred, pos_label=1, average="binary", zero_division=0
    )

    bal_acc = 0.5 * (float(r0) + float(r1))

    return ThresholdMetrics(
        thr=float(thr),
        alert_rate=float(pred.mean()),
        prec1=float(p1),
        rec1=float(r1),
        f1_1=float(f1),
        bal_acc=float(bal_acc),
    )


def score_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict:
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba).astype(float)

    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "positive_rate": float(y_true.mean()),
    }
