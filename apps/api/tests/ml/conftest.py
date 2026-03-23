from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

# 21 features matching FEATURE_NAMES in ml/train.py
FEATURE_NAMES_21 = [
    "icf_per60",
    "ixg_per60",
    "xgf_pct_5v5",
    "cf_pct_adj",
    "scf_per60",
    "scf_pct",
    "p1_per60",
    "toi_ev",
    "toi_pp",
    "g_per60",
    "ixg_per60_curr",
    "g_minus_ixg",
    "sh_pct_delta",
    "pdo",
    "pp_unit",
    "oi_sh_pct",
    "elc_flag",
    "contract_year_flag",
    "post_extension_flag",
    "age",
    "icf_per60_delta",
]


@pytest.fixture
def tiny_model() -> xgb.XGBClassifier:
    """21-feature XGBoost model trained on 40 synthetic rows for fast tests."""
    rng = np.random.default_rng(42)
    X = rng.random((40, 21)).astype(np.float32)
    y = (X[:, 0] > 0.5).astype(int)
    X_df = pd.DataFrame(X, columns=FEATURE_NAMES_21)
    model = xgb.XGBClassifier(
        n_estimators=5,
        max_depth=2,
        random_state=42,
        eval_metric="logloss",
    )
    model.fit(X_df, y)
    return model
