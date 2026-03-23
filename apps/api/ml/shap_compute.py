from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import shap

if TYPE_CHECKING:
    import xgboost as xgb


def compute_shap(
    model: xgb.XGBClassifier,
    X: np.ndarray,
    feature_names: list[str],
) -> list[dict[str, dict[str, float]]]:
    """Compute top-3 SHAP values per player for a binary XGBoost classifier.

    Args:
        model: Trained XGBoost classifier.
        X: Feature matrix of shape (n_players, n_features).
        feature_names: Column names corresponding to X columns.

    Returns:
        List of dicts with shape [{"breakout": {"feature_name": shap_value, ...}}, ...]
        Each player's dict contains the top-3 features by absolute SHAP value.
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    # shap_values shape: (n_players, n_features)
    results = []
    for row_shap in shap_values:
        top3_idx = np.argsort(np.abs(row_shap))[::-1][:3]
        top3 = {feature_names[i]: float(row_shap[i]) for i in top3_idx}
        results.append({"breakout": top3})

    return results
