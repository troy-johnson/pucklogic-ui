from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score


@dataclass(frozen=True)
class MetricsResult:
    auc_roc: float
    precision_at_50: float
    recall_at_50: float


def compute_metrics(y_true: list[int], y_pred_proba: list[float]) -> MetricsResult:
    """Compute AUC-ROC, precision@50, and recall@50 for a binary classifier.

    Args:
        y_true: Ground-truth binary labels (0 or 1).
        y_pred_proba: Predicted probabilities for the positive class.

    Returns:
        MetricsResult with auc_roc, precision_at_50, recall_at_50.
    """
    arr_true = np.array(y_true)
    arr_proba = np.array(y_pred_proba)

    auc_roc = float(roc_auc_score(arr_true, arr_proba))

    k = min(50, len(arr_true))
    top_k_idx = np.argsort(arr_proba)[::-1][:k]
    top_k_labels = arr_true[top_k_idx]

    true_positives = int(top_k_labels.sum())
    total_positives = int(arr_true.sum())

    precision_at_50 = true_positives / k if k > 0 else 0.0
    recall_at_50 = true_positives / total_positives if total_positives > 0 else 0.0

    return MetricsResult(
        auc_roc=auc_roc,
        precision_at_50=precision_at_50,
        recall_at_50=recall_at_50,
    )
