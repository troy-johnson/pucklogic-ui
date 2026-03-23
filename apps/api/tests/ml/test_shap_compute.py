from __future__ import annotations

import numpy as np
import pytest
import xgboost as xgb

from ml.shap_compute import compute_shap


@pytest.fixture
def tiny_model() -> xgb.XGBClassifier:
    """3-feature XGBoost model trained on 20 synthetic rows."""
    rng = np.random.default_rng(42)
    X = rng.random((20, 3)).astype(np.float32)
    y = (X[:, 0] > 0.5).astype(int)
    import pandas as pd

    X_df = pd.DataFrame(X, columns=["feat_a", "feat_b", "feat_c"])
    model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=42, eval_metric="logloss")
    model.fit(X_df, y)
    return model


class TestComputeShap:
    def test_returns_list_of_dicts(self, tiny_model):
        rng = np.random.default_rng(0)
        X = rng.random((5, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        assert isinstance(result, list)
        assert len(result) == 5
        for item in result:
            assert isinstance(item, dict)

    def test_each_dict_has_breakout_key(self, tiny_model):
        rng = np.random.default_rng(1)
        X = rng.random((3, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        for item in result:
            assert "breakout" in item

    def test_top3_has_at_most_3_entries(self, tiny_model):
        rng = np.random.default_rng(2)
        X = rng.random((10, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        for item in result:
            assert len(item["breakout"]) <= 3

    def test_feature_names_are_keys(self, tiny_model):
        rng = np.random.default_rng(3)
        X = rng.random((4, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        all_keys = set()
        for item in result:
            all_keys.update(item["breakout"].keys())
        assert all_keys.issubset({"feat_a", "feat_b", "feat_c"})

    def test_values_are_floats(self, tiny_model):
        rng = np.random.default_rng(4)
        X = rng.random((4, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        for item in result:
            for v in item["breakout"].values():
                assert isinstance(v, float)

    def test_single_row(self, tiny_model):
        rng = np.random.default_rng(5)
        X = rng.random((1, 3)).astype(np.float32)
        result = compute_shap(tiny_model, X, ["feat_a", "feat_b", "feat_c"])
        assert len(result) == 1
