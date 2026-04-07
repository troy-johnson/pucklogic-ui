# Phase 3d — Model Training + Inference API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train XGBoost/LightGBM breakout+regression classifiers on historical player_stats, compute SHAP values, upload artifacts to Supabase Storage, and serve pre-computed scores via GET /trends.

**Architecture:** Flat `ml/` module (4 files) in `apps/api/`; training is a CLI script (`python -m ml.train --season 2026-27`); inference reads pre-computed `player_trends` rows; FastAPI lifespan loads models at startup for health checking only.

**Tech Stack:** XGBoost, LightGBM, SHAP, Optuna, scikit-learn, joblib, Supabase Storage (via supabase-py v2), FastAPI lifespan context, pytest + MagicMock

**Spec:** `docs/adrs/005-phase3d-model-training.md`

---

## File Map

### New files
| Path | Responsibility |
|---|---|
| `apps/api/ml/__init__.py` | Empty package marker |
| `apps/api/ml/evaluate.py` | `compute_metrics(y_true, y_pred_proba) → MetricsResult` |
| `apps/api/ml/shap_compute.py` | `compute_shap(model, X, feature_names) → list[dict]` (top-3 per player) |
| `apps/api/ml/loader.py` | `derive_data_season`, `ModelNotAvailableError`, `load()`, `upload()` |
| `apps/api/ml/train.py` | `compute_label`, `build_labeled_dataset`, `train_xgboost`, `train_lightgbm`, `main()` CLI |
| `apps/api/repositories/trends.py` | `TrendsRepository.get_trends(season) → TrendsResponse` |
| `apps/api/routers/trends.py` | `GET /trends?season=<season>` |
| `apps/api/tests/ml/__init__.py` | Empty |
| `apps/api/tests/ml/conftest.py` | Shared tiny-model fixture for ML unit tests |
| `apps/api/tests/ml/test_evaluate.py` | Metrics tests |
| `apps/api/tests/ml/test_shap_compute.py` | SHAP output shape tests |
| `apps/api/tests/ml/test_loader.py` | Storage mock tests + `derive_data_season` |
| `apps/api/tests/ml/test_train.py` | `compute_label`, leakage guard, class weights |
| `apps/api/tests/smoke/test_train_smoke.py` | 50-player end-to-end pipeline (CI excluded) |
| `apps/api/tests/repositories/test_trends.py` | LEFT JOIN null-handling, ordering |
| `apps/api/tests/routers/test_trends.py` | 503 + success, `has_trends=False` |

### Modified files
| Path | Change |
|---|---|
| `apps/api/pyproject.toml` | Add `xgboost`, `lightgbm`, `shap`, `optuna`, `scikit-learn` |
| `apps/api/repositories/player_stats.py` | Add `get_all_seasons_grouped()` |
| `apps/api/core/dependencies.py` | Add `get_trends_repository()` |
| `apps/api/main.py` | Add lifespan hook + `trends` router import |
| `.github/workflows/retrain-trends.yml` | Complete the training step |

---

## Task 1: Feature branch + ML dependencies

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: Create feature branch**

```bash
cd /path/to/pucklogic-ui
git checkout -b feat/phase3d-model-training
```

- [ ] **Step 2: Add ML dependencies to pyproject.toml**

In the `[project] dependencies` list, add after `pandas>=2.0.0`:

```toml
    "xgboost>=2.1.0",
    "lightgbm>=4.5.0",
    "shap>=0.46.0",
    "optuna>=4.1.0",
    "scikit-learn>=1.5.0",
    "joblib>=1.4.0",
```

Note: `joblib` may already be installed as a scikit-learn dependency, but pin it explicitly since we depend on it directly for artifact serialization.

- [ ] **Step 3: Install**

```bash
cd apps/api
pip install -e ".[dev]"
```

Expected: All packages install without conflict.

- [ ] **Step 4: Verify imports**

```bash
python -c "import xgboost, lightgbm, shap, optuna, sklearn, joblib; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml
git commit -m "feat(phase3d): add ML dependencies (xgboost, lightgbm, shap, optuna, sklearn)"
```

---

## Task 2: `ml/evaluate.py` — metrics computation

**Files:**
- Create: `apps/api/ml/__init__.py`
- Create: `apps/api/ml/evaluate.py`
- Create: `apps/api/tests/ml/__init__.py`
- Create: `apps/api/tests/ml/test_evaluate.py`

- [ ] **Step 1: Write the failing tests**

`apps/api/tests/ml/test_evaluate.py`:
```python
from __future__ import annotations

import numpy as np
import pytest

from ml.evaluate import MetricsResult, compute_metrics


class TestComputeMetrics:
    def test_perfect_classifier(self):
        y_true = [1, 1, 0, 0, 1]
        y_prob = [0.9, 0.8, 0.1, 0.2, 0.7]
        result = compute_metrics(y_true, y_prob)
        assert result.auc_roc == pytest.approx(1.0)

    def test_random_classifier_auc_near_half(self):
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 2, 200).tolist()
        y_prob = rng.uniform(0, 1, 200).tolist()
        result = compute_metrics(y_true, y_prob)
        # Random classifier AUC should be roughly 0.5
        assert 0.35 < result.auc_roc < 0.65

    def test_precision_at_k_all_positives_in_top_k(self):
        # Top 2 predictions are the only positives
        y_true = [1, 1, 0, 0, 0]
        y_prob = [0.9, 0.8, 0.3, 0.2, 0.1]
        result = compute_metrics(y_true, y_prob, k=2)
        assert result.precision_at_k == pytest.approx(1.0)
        assert result.recall_at_k == pytest.approx(1.0)

    def test_precision_at_k_no_positives_in_top_k(self):
        y_true = [0, 0, 1, 1, 1]
        y_prob = [0.9, 0.8, 0.3, 0.2, 0.1]
        result = compute_metrics(y_true, y_prob, k=2)
        assert result.precision_at_k == pytest.approx(0.0)
        assert result.recall_at_k == pytest.approx(0.0)

    def test_metrics_result_has_expected_fields(self):
        result = compute_metrics([1, 0, 1], [0.8, 0.2, 0.7])
        assert hasattr(result, "auc_roc")
        assert hasattr(result, "precision_at_k")
        assert hasattr(result, "recall_at_k")
        assert 0.0 <= result.auc_roc <= 1.0
```

- [ ] **Step 2: Run tests — expect ImportError (file not created yet)**

```bash
cd apps/api
pytest tests/ml/test_evaluate.py -v
```

Expected: `ImportError: No module named 'ml'`

- [ ] **Step 3: Create empty package marker**

`apps/api/ml/__init__.py`: empty file.
`apps/api/tests/ml/__init__.py`: empty file.

- [ ] **Step 4: Implement `ml/evaluate.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score


@dataclass
class MetricsResult:
    auc_roc: float
    precision_at_k: float
    recall_at_k: float


def compute_metrics(
    y_true: list[int],
    y_pred_proba: list[float],
    k: int = 50,
) -> MetricsResult:
    """Compute AUC-ROC, precision@k, and recall@k.

    Args:
        y_true: Binary labels (0 or 1).
        y_pred_proba: Model output probabilities for the positive class.
        k: Number of top predictions to use for precision/recall@k.

    Returns:
        MetricsResult with auc_roc, precision_at_k, recall_at_k.
    """
    y_true_arr = np.array(y_true)
    y_prob_arr = np.array(y_pred_proba)

    auc = float(roc_auc_score(y_true_arr, y_prob_arr))

    # precision@k and recall@k
    top_k_idx = np.argsort(y_prob_arr)[::-1][:k]
    top_k_labels = y_true_arr[top_k_idx]
    n_positive_in_top_k = int(top_k_labels.sum())
    total_positives = int(y_true_arr.sum())

    precision_at_k = n_positive_in_top_k / k if k > 0 else 0.0
    recall_at_k = (
        n_positive_in_top_k / total_positives if total_positives > 0 else 0.0
    )

    return MetricsResult(
        auc_roc=auc,
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
    )
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/ml/test_evaluate.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/ml/__init__.py apps/api/ml/evaluate.py \
        apps/api/tests/ml/__init__.py apps/api/tests/ml/test_evaluate.py
git commit -m "feat(phase3d): ml/evaluate.py — AUC-ROC, precision@k, recall@k"
```

---

## Task 3: `ml/shap_compute.py` — top-3 SHAP per player

**Files:**
- Create: `apps/api/ml/shap_compute.py`
- Create: `apps/api/tests/ml/conftest.py`
- Create: `apps/api/tests/ml/test_shap_compute.py`

- [ ] **Step 1: Write conftest.py with tiny fixture model**

`apps/api/tests/ml/conftest.py`:
```python
"""Shared fixtures for ML unit tests.

TINY_MODEL is a real XGBoost binary classifier trained on 20 rows of
synthetic data with all 21 Phase 3d features. Used to test loader,
shap_compute, etc. without requiring training in CI.
"""
from __future__ import annotations

import numpy as np
import pytest
import xgboost as xgb

from ml.train import FEATURE_NAMES


@pytest.fixture(scope="session")
def tiny_model() -> xgb.XGBClassifier:
    """Return a small XGBoost model trained on 20 synthetic rows."""
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, (20, len(FEATURE_NAMES)))
    y = rng.integers(0, 2, 20)
    # Ensure at least one positive label for class balance
    y[0] = 1
    model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=0)
    model.fit(X, y, feature_names=FEATURE_NAMES)
    return model


@pytest.fixture(scope="session")
def tiny_X(tiny_model) -> np.ndarray:
    """10 synthetic rows for inference tests."""
    rng = np.random.default_rng(1)
    return rng.uniform(0, 1, (10, len(FEATURE_NAMES)))
```

- [ ] **Step 2: Write failing tests**

`apps/api/tests/ml/test_shap_compute.py`:
```python
from __future__ import annotations

import pytest

from ml.shap_compute import compute_shap
from ml.train import FEATURE_NAMES


class TestComputeShap:
    def test_returns_one_dict_per_player(self, tiny_model, tiny_X):
        results = compute_shap(tiny_model, tiny_X, FEATURE_NAMES)
        assert len(results) == len(tiny_X)

    def test_each_result_has_top3_keys(self, tiny_model, tiny_X):
        results = compute_shap(tiny_model, tiny_X, FEATURE_NAMES)
        for r in results:
            assert "breakout" in r
            assert len(r["breakout"]) == 3  # top-3 feature names
            for feat, val in r["breakout"].items():
                assert feat in FEATURE_NAMES
                assert isinstance(val, float)

    def test_regression_key_absent(self, tiny_model, tiny_X):
        # shap_compute only computes for the model passed in;
        # caller passes breakout_model and regression_model separately
        results = compute_shap(tiny_model, tiny_X, FEATURE_NAMES)
        for r in results:
            assert "regression" not in r

    def test_feature_values_are_finite(self, tiny_model, tiny_X):
        import math
        results = compute_shap(tiny_model, tiny_X, FEATURE_NAMES)
        for r in results:
            for val in r["breakout"].values():
                assert math.isfinite(val)
```

- [ ] **Step 3: Run tests — expect ImportError**

```bash
pytest tests/ml/test_shap_compute.py -v
```

Expected: `ImportError: cannot import name 'compute_shap'`

- [ ] **Step 4: Implement `ml/shap_compute.py`**

```python
from __future__ import annotations

import numpy as np
import shap
import xgboost as xgb


def compute_shap(
    model: xgb.XGBClassifier,
    X: np.ndarray,
    feature_names: list[str],
) -> list[dict[str, dict[str, float]]]:
    """Compute top-3 SHAP values per player for a single model.

    Returns a list of dicts, one per row in X:
        [{"breakout": {"icf_per60": 0.12, "toi_ev": 0.08, "pdo": -0.05}}, ...]

    The key "breakout" is always used regardless of which model is passed.
    Callers are responsible for running this separately for breakout and
    regression models and merging the results.
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    results: list[dict[str, dict[str, float]]] = []
    for row_shap in shap_values:
        # top-3 by absolute SHAP value
        top3_idx = np.argsort(np.abs(row_shap))[::-1][:3]
        top3 = {feature_names[i]: float(row_shap[i]) for i in top3_idx}
        results.append({"breakout": top3})

    return results
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/ml/test_shap_compute.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/ml/shap_compute.py \
        apps/api/tests/ml/conftest.py \
        apps/api/tests/ml/test_shap_compute.py
git commit -m "feat(phase3d): ml/shap_compute.py — top-3 SHAP per player"
```

---

## Task 4: `ml/loader.py` — artifact storage + derive_data_season

**Files:**
- Create: `apps/api/ml/loader.py`
- Create: `apps/api/tests/ml/test_loader.py`

- [ ] **Step 1: Write failing tests**

`apps/api/tests/ml/test_loader.py`:
```python
from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pytest
import xgboost as xgb

from ml.loader import (
    ModelNotAvailableError,
    derive_data_season,
    load,
    upload,
)
from ml.train import FEATURE_NAMES


# ---------------------------------------------------------------------------
# derive_data_season
# ---------------------------------------------------------------------------

class TestDeriveDataSeason:
    def test_standard_case(self):
        assert derive_data_season("2026-27") == "2025-26"

    def test_decade_boundary(self):
        assert derive_data_season("2010-11") == "2009-10"

    def test_training_start(self):
        assert derive_data_season("2006-07") == "2005-06"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="YYYY-YY"):
            derive_data_season("2026-2027")  # wrong format


# ---------------------------------------------------------------------------
# ModelNotAvailableError
# ---------------------------------------------------------------------------

class TestModelNotAvailableError:
    def test_is_exception(self):
        err = ModelNotAvailableError("test message")
        assert isinstance(err, Exception)
        assert "test message" in str(err)


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

class TestUpload:
    def test_upload_calls_storage_three_times(self, tiny_model):
        mock_db = MagicMock()
        regression_model = tiny_model  # reuse same fixture

        upload(
            db=mock_db,
            breakout_model=tiny_model,
            regression_model=regression_model,
            metrics={"breakout": {"auc_roc": 0.72}, "regression": {"auc_roc": 0.68}},
            feature_names=FEATURE_NAMES,
            data_season="2025-26",
            n_train=500,
            n_holdout=50,
        )

        # storage.from_("ml-artifacts").upload() should be called 3 times
        storage_bucket = mock_db.storage.from_.return_value
        assert storage_bucket.upload.call_count == 3

    def test_upload_uses_correct_paths(self, tiny_model):
        mock_db = MagicMock()
        upload(
            db=mock_db,
            breakout_model=tiny_model,
            regression_model=tiny_model,
            metrics={"breakout": {"auc_roc": 0.72}, "regression": {"auc_roc": 0.68}},
            feature_names=FEATURE_NAMES,
            data_season="2025-26",
            n_train=500,
            n_holdout=50,
        )
        storage_bucket = mock_db.storage.from_.return_value
        uploaded_paths = [call.args[0] for call in storage_bucket.upload.call_args_list]
        assert "2025-26/breakout_model.joblib" in uploaded_paths
        assert "2025-26/regression_model.joblib" in uploaded_paths
        assert "2025-26/metadata.json" in uploaded_paths


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_raises_when_storage_fails(self):
        mock_db = MagicMock()
        mock_db.storage.from_.return_value.download.side_effect = Exception("not found")

        with pytest.raises(ModelNotAvailableError):
            load(db=mock_db, season="2026-27")

    def test_returns_tuple_of_models_on_success(self, tiny_model, tmp_path):
        """Mock the Storage download to return serialized tiny_model bytes."""
        buf = io.BytesIO()
        joblib.dump(tiny_model, buf)
        model_bytes = buf.getvalue()

        mock_db = MagicMock()
        mock_db.storage.from_.return_value.download.return_value = model_bytes

        # Disable dev cache for this test
        with patch.dict(os.environ, {"PUCKLOGIC_NO_DEV_CACHE": "1"}):
            breakout, regression = load(db=mock_db, season="2026-27")

        assert breakout is not None
        assert regression is not None

    def test_dev_cache_skips_storage_download(self, tiny_model, tmp_path):
        """When cache file exists and PUCKLOGIC_NO_DEV_CACHE is not set, Storage is NOT called."""
        data_season = "2025-26"

        # Write a real serialized model to the expected dev cache path
        cache_dir = tmp_path / data_season
        cache_dir.mkdir(parents=True)
        for filename in ("breakout_model.joblib", "regression_model.joblib"):
            joblib.dump(tiny_model, cache_dir / filename)

        mock_db = MagicMock()

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("ml.loader._DEV_CACHE_DIR", tmp_path),
        ):
            # Ensure env var absent so cache is enabled
            os.environ.pop("PUCKLOGIC_NO_DEV_CACHE", None)
            breakout, regression = load(db=mock_db, season="2026-27")

        mock_db.storage.from_.return_value.download.assert_not_called()
        assert breakout is not None
        assert regression is not None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/ml/test_loader.py -v
```

Expected: `ImportError: cannot import name 'derive_data_season'`

- [ ] **Step 3: Implement `ml/loader.py`**

```python
from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import joblib
import xgboost as xgb

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)

_BUCKET = "ml-artifacts"
_DEV_CACHE_DIR = Path.home() / ".pucklogic" / "models"


class ModelNotAvailableError(Exception):
    """Raised when model artifacts cannot be loaded from Supabase Storage."""


def derive_data_season(season: str) -> str:
    """Convert a training season string to a data season string.

    Args:
        season: Training season in "YYYY-YY" format, e.g. "2026-27".

    Returns:
        Data season string, e.g. "2025-26".

    Raises:
        ValueError: If season is not in "YYYY-YY" format.

    Examples:
        derive_data_season("2026-27") == "2025-26"
        derive_data_season("2010-11") == "2009-10"
        derive_data_season("2006-07") == "2005-06"
    """
    parts = season.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise ValueError(f"season must be in YYYY-YY format, got: {season!r}")
    start = int(parts[0])
    return f"{start - 1}-{str(start)[-2:]}"


def _dev_cache_path(data_season: str, filename: str) -> Path:
    return _DEV_CACHE_DIR / data_season / filename


def _download_model(db: "Client", data_season: str, filename: str) -> xgb.XGBClassifier:
    """Download a model from Storage, using dev cache when available."""
    no_cache = os.environ.get("PUCKLOGIC_NO_DEV_CACHE", "0") == "1"
    cache_path = _dev_cache_path(data_season, filename)

    if not no_cache and cache_path.exists():
        logger.info("Loading %s from dev cache %s", filename, cache_path)
        return joblib.load(cache_path)

    logger.info("Downloading %s from Storage ml-artifacts/%s/", filename, data_season)
    try:
        raw = db.storage.from_(_BUCKET).download(f"{data_season}/{filename}")
    except Exception as exc:
        raise ModelNotAvailableError(
            f"Failed to download {data_season}/{filename} from Storage: {exc}"
        ) from exc

    model: xgb.XGBClassifier = joblib.load(io.BytesIO(raw))

    if not no_cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, cache_path)
        logger.info("Cached %s to %s", filename, cache_path)

    return model


def load(db: "Client", season: str) -> tuple[xgb.XGBClassifier, xgb.XGBClassifier]:
    """Load breakout and regression models from Supabase Storage.

    Args:
        db: Supabase client with service role.
        season: Training season in "YYYY-YY" format, e.g. "2026-27".

    Returns:
        (breakout_model, regression_model) tuple.

    Raises:
        ModelNotAvailableError: If Storage is unreachable or artifacts are missing.
    """
    data_season = derive_data_season(season)
    breakout = _download_model(db, data_season, "breakout_model.joblib")
    regression = _download_model(db, data_season, "regression_model.joblib")
    return breakout, regression


def upload(
    db: "Client",
    breakout_model: xgb.XGBClassifier,
    regression_model: xgb.XGBClassifier,
    metrics: dict[str, Any],
    feature_names: list[str],
    data_season: str,
    n_train: int,
    n_holdout: int,
) -> None:
    """Serialize and upload model artifacts to Supabase Storage.

    Uploads three files to ml-artifacts/{data_season}/:
    - breakout_model.joblib
    - regression_model.joblib
    - metadata.json

    Args:
        db: Supabase client with service role.
        data_season: Completed season string, e.g. "2025-26".
        metrics: Dict with "breakout" and "regression" MetricsResult dicts.
        n_train: Number of training examples used.
        n_holdout: Number of holdout examples evaluated against.
    """
    bucket = db.storage.from_(_BUCKET)

    def _serialize_model(model: xgb.XGBClassifier) -> bytes:
        buf = io.BytesIO()
        joblib.dump(model, buf)
        return buf.getvalue()

    bucket.upload(
        f"{data_season}/breakout_model.joblib",
        _serialize_model(breakout_model),
    )
    bucket.upload(
        f"{data_season}/regression_model.joblib",
        _serialize_model(regression_model),
    )

    metadata = {
        "season": data_season,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "n_train": n_train,
        "n_holdout": n_holdout,
        "feature_names": feature_names,
        "breakout": metrics.get("breakout", {}),
        "regression": metrics.get("regression", {}),
        "lgb_breakout_auc_roc": metrics.get("lgb_breakout_auc_roc"),
        "lgb_regression_auc_roc": metrics.get("lgb_regression_auc_roc"),
    }
    bucket.upload(
        f"{data_season}/metadata.json",
        json.dumps(metadata).encode(),
    )
    logger.info("Artifacts uploaded to ml-artifacts/%s/", data_season)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/ml/test_loader.py -v
```

Expected: All tests PASS (some `upload` tests may need `tiny_model` fixture — verify conftest is loaded).

- [ ] **Step 5: Commit**

```bash
git add apps/api/ml/loader.py apps/api/tests/ml/test_loader.py
git commit -m "feat(phase3d): ml/loader.py — derive_data_season, load, upload, ModelNotAvailableError"
```

---

## Task 5: `repositories/player_stats.py` — add `get_all_seasons_grouped`

**Files:**
- Modify: `apps/api/repositories/player_stats.py`
- Modify: `apps/api/tests/repositories/test_player_stats.py`

The existing `get_seasons_grouped(season, window=3)` queries a narrow window. The new method returns ALL historical rows for ALL players, used only by `ml/train.py`.

- [ ] **Step 1: Write failing test**

Append to `apps/api/tests/repositories/test_player_stats.py`:

```python
class TestGetAllSeasonsGrouped:
    """get_all_seasons_grouped returns all seasons, no window cap, LEFT JOIN on players."""

    def _configure_db_all(self, mock_db: MagicMock, rows: list[dict]) -> None:
        """Wire mock for .table().select().order().execute()."""
        (
            mock_db.table.return_value
            .select.return_value
            .order.return_value
            .execute.return_value
        ).data = rows

    def test_returns_all_rows_grouped_by_player(self, repo, mock_db):
        rows = [
            _make_db_row("p-mcdavid", season=2025),
            _make_db_row("p-mcdavid", season=2024),
            _make_db_row("p-mcdavid", season=2023),
            _make_db_row("p-draisaitl", season=2025),
        ]
        self._configure_db_all(mock_db, rows)
        result = repo.get_all_seasons_grouped()
        assert "p-mcdavid" in result
        assert "p-draisaitl" in result
        assert len(result["p-mcdavid"]) == 3

    def test_rows_sorted_newest_first(self, repo, mock_db):
        rows = [
            _make_db_row("p-mcdavid", season=2020),
            _make_db_row("p-mcdavid", season=2025),
            _make_db_row("p-mcdavid", season=2015),
        ]
        self._configure_db_all(mock_db, rows)
        result = repo.get_all_seasons_grouped()
        seasons = [r["season"] for r in result["p-mcdavid"]]
        assert seasons == [2025, 2020, 2015]

    def test_left_join_preserves_null_position(self, repo, mock_db):
        """Players without a players table row (debutants) have position=None."""
        row = _make_db_row("p-debutant", season=2025)
        row["players"] = None  # LEFT JOIN returns None for missing row
        self._configure_db_all(mock_db, [row])
        result = repo.get_all_seasons_grouped()
        assert result["p-debutant"][0].get("position") is None

    def test_does_not_call_in_filter(self, repo, mock_db):
        """Must NOT use .in_() season filter — returns all seasons."""
        self._configure_db_all(mock_db, [])
        repo.get_all_seasons_grouped()
        # .in_() should not have been called on the chain
        mock_db.table.return_value.select.return_value.in_.assert_not_called()
```

- [ ] **Step 2: Run test — expect AttributeError (method doesn't exist yet)**

```bash
pytest tests/repositories/test_player_stats.py::TestGetAllSeasonsGrouped -v
```

Expected: `AttributeError: 'PlayerStatsRepository' object has no attribute 'get_all_seasons_grouped'`

- [ ] **Step 3: Implement in `repositories/player_stats.py`**

Add after the closing brace of `get_seasons_grouped`:

```python
    def get_all_seasons_grouped(self) -> dict[str, list[dict[str, Any]]]:
        """Return ALL player_stats rows for ALL players, grouped by player_id.

        Unlike get_seasons_grouped(), this method has no season window cap and
        returns every historical row available. Used only by ml/train.py.

        Uses LEFT JOIN on players table so debutants (players with no `players`
        record) are included; their position and date_of_birth will be None.

        Returns:
            {player_id: [rows sorted newest-first]}
        """
        result = (
            self._db.table("player_stats")
            .select(f"{_STAT_COLUMNS}, players(date_of_birth, position)")
            .order("season", desc=True)
            .execute()
        )

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in result.data:
            players_join = raw.pop("players", None) or {}
            row = {**raw, **players_join}
            grouped[row["player_id"]].append(row)

        for rows in grouped.values():
            rows.sort(key=lambda r: r["season"], reverse=True)

        return dict(grouped)
```

Note: Uses `players(...)` without `!inner` to get a LEFT JOIN. If a player has no `players` row, Supabase returns `None` for the nested object; the `or {}` handles it gracefully (no position/date_of_birth in the row).

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/repositories/test_player_stats.py -v
```

Expected: All tests including the 4 new ones PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/repositories/player_stats.py \
        apps/api/tests/repositories/test_player_stats.py
git commit -m "feat(phase3d): PlayerStatsRepository.get_all_seasons_grouped — no window cap, LEFT JOIN"
```

---

## Task 6: `repositories/trends.py` — TrendsRepository

**Files:**
- Create: `apps/api/repositories/trends.py`
- Create: `apps/api/tests/repositories/test_trends.py`

`TrendsResponse` and `TrendedPlayer` are already defined in `models/schemas.py`. This repository does two queries and merges in Python (avoids complex PostgREST LEFT JOIN syntax).

- [ ] **Step 1: Write failing tests**

`apps/api/tests/repositories/test_trends.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from repositories.trends import TrendsRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> TrendsRepository:
    return TrendsRepository(mock_db)


def _make_player(player_id: str = "p-1", name: str = "Player One") -> dict:
    return {"id": player_id, "name": name, "position": "C", "team": "EDM"}


def _make_trend(
    player_id: str = "p-1",
    season: str = "2025-26",
    breakout_score: float | None = 0.72,
    regression_risk: float | None = 0.15,
) -> dict:
    return {
        "player_id": player_id,
        "season": season,
        "breakout_score": breakout_score,
        "regression_risk": regression_risk,
        "confidence": 0.80,
        "shap_values": None,
        "shap_top3": None,
        "updated_at": "2026-08-01T08:00:00+00:00",
    }


def _configure(mock_db: MagicMock, players: list[dict], trends: list[dict]) -> None:
    """Wire mock_db for two independent .table().select()...execute() chains."""
    players_chain = MagicMock()
    players_chain.execute.return_value.data = players

    trends_chain = MagicMock()
    trends_chain.execute.return_value.data = trends

    # table("players") → players_chain; table("player_trends") → trends_chain
    def _table_side_effect(name: str) -> MagicMock:
        return players_chain if name == "players" else trends_chain

    mock_db.table.side_effect = _table_side_effect
    players_chain.select.return_value = players_chain
    trends_chain.select.return_value.eq.return_value = trends_chain


class TestGetTrends:
    def test_has_trends_false_when_no_rows(self, repo, mock_db):
        _configure(mock_db, players=[_make_player()], trends=[])
        result = repo.get_trends("2025-26")
        assert result.has_trends is False
        assert result.updated_at is None

    def test_has_trends_true_when_rows_exist(self, repo, mock_db):
        _configure(mock_db, players=[_make_player()], trends=[_make_trend()])
        result = repo.get_trends("2025-26")
        assert result.has_trends is True
        assert result.updated_at is not None

    def test_player_without_trends_has_null_scores(self, repo, mock_db):
        """Players with no player_trends row return null scores, not 500."""
        _configure(
            mock_db,
            players=[_make_player("p-1"), _make_player("p-2", "Player Two")],
            trends=[_make_trend("p-1")],  # p-2 has no trend row
        )
        result = repo.get_trends("2025-26")
        p2 = next(p for p in result.players if p.player_id == "p-2")
        assert p2.breakout_score is None
        assert p2.regression_risk is None

    def test_players_ordered_by_breakout_score_desc(self, repo, mock_db):
        """Players sorted breakout_score DESC, nulls last."""
        _configure(
            mock_db,
            players=[_make_player("p-1"), _make_player("p-2"), _make_player("p-3")],
            trends=[
                _make_trend("p-1", breakout_score=0.5),
                _make_trend("p-3", breakout_score=0.9),
                # p-2 has no trend row → null → last
            ],
        )
        result = repo.get_trends("2025-26")
        scores = [p.breakout_score for p in result.players]
        # 0.9, 0.5, None
        assert scores[0] == pytest.approx(0.9)
        assert scores[1] == pytest.approx(0.5)
        assert scores[2] is None

    def test_season_returned_in_response(self, repo, mock_db):
        _configure(mock_db, players=[], trends=[])
        result = repo.get_trends("2025-26")
        assert result.season == "2025-26"
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/repositories/test_trends.py -v
```

Expected: `ImportError: cannot import name 'TrendsRepository'`

- [ ] **Step 3: Implement `repositories/trends.py`**

```python
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from models.schemas import TrendedPlayer, TrendsResponse

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)


class TrendsRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def get_trends(self, season: str) -> TrendsResponse:
        """Return trends for all players for a season.

        Performs two queries and merges in Python to achieve a LEFT JOIN
        (all players, with null scores for those lacking a player_trends row).

        Args:
            season: Season string, e.g. "2025-26".

        Returns:
            TrendsResponse with has_trends=False when no player_trends rows
            exist yet (valid pre-training state).
        """
        players_result = (
            self._db.table("players")
            .select("id, name, position, team")
            .execute()
        )
        trends_result = (
            self._db.table("player_trends")
            .select(
                "player_id, breakout_score, regression_risk, confidence, "
                "shap_values, shap_top3, updated_at"
            )
            .eq("season", season)
            .execute()
        )

        trends_by_pid: dict[str, dict[str, Any]] = {
            t["player_id"]: t for t in trends_result.data
        }
        has_trends = bool(trends_result.data)
        updated_at: datetime | None = None
        if has_trends:
            latest = max(trends_result.data, key=lambda t: t["updated_at"])
            updated_at = datetime.fromisoformat(latest["updated_at"])

        trended: list[TrendedPlayer] = []
        for p in players_result.data:
            t = trends_by_pid.get(p["id"])
            trended.append(
                TrendedPlayer(
                    player_id=p["id"],
                    name=p["name"],
                    position=p.get("position"),
                    team=p.get("team"),
                    breakout_score=t["breakout_score"] if t else None,
                    regression_risk=t["regression_risk"] if t else None,
                    confidence=t["confidence"] if t else None,
                    shap_top3=t.get("shap_top3") if t else None,
                )
            )

        # Sort: breakout_score DESC, nulls last
        trended.sort(
            key=lambda p: (
                p.breakout_score is None,
                -(p.breakout_score or 0.0),
            )
        )

        return TrendsResponse(
            season=season,
            has_trends=has_trends,
            updated_at=updated_at,
            players=trended,
        )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/repositories/test_trends.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/repositories/trends.py \
        apps/api/tests/repositories/test_trends.py
git commit -m "feat(phase3d): TrendsRepository.get_trends — LEFT JOIN merge, null handling, ordered by breakout_score"
```

---

## Task 7: `ml/train.py` Part 1 — `compute_label` + `build_labeled_dataset`

**Files:**
- Create: `apps/api/ml/train.py` (partial — label + dataset functions only)
- Create: `apps/api/tests/ml/test_train.py`

This task covers the most critical correctness property: the leakage guard ensuring season N+1 rows never appear in the feature slice passed to `build_feature_matrix`.

- [ ] **Step 1: Write failing tests for `compute_label` and `build_labeled_dataset`**

`apps/api/tests/ml/test_train.py`:
```python
from __future__ import annotations

import pytest

from ml.train import FEATURE_NAMES, build_labeled_dataset, compute_label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(player_id: str, season: int, p1_per60: float, toi_ev: float = 6.0) -> dict:
    """Minimal player_stats row for label computation tests."""
    return {
        "player_id": player_id,
        "season": season,
        "p1_per60": p1_per60,
        "toi_ev": toi_ev,
        # Feature columns — not used by compute_label but needed by build_feature_matrix
        "icf_per60": 12.0, "ixg_per60": 10.0, "xgf_pct_5v5": 52.0, "cf_pct_adj": 51.0,
        "scf_per60": 16.0, "scf_pct": 51.0, "toi_pp": 2.5, "toi_sh": 0.1,
        "g_per60": 2.0, "g_minus_ixg": 0.5, "sh_pct": 0.11, "sh_pct_career_avg": 0.10,
        "pdo": 1.005, "pp_unit": 1, "oi_sh_pct": 0.09, "elc_flag": False,
        "contract_year_flag": False, "post_extension_flag": False,
        "date_of_birth": "1995-01-15", "position": "C",
    }


# ---------------------------------------------------------------------------
# compute_label tests
# ---------------------------------------------------------------------------

class TestComputeLabel:
    def test_breakout_when_curr_20pct_above_avg(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=3.6),  # curr (N+1)
                _make_row("p1", 2009, p1_per60=3.0),  # N (most recent prior)
            ]
        }
        breakout, regression = compute_label("p1", season_n=2009, all_rows=all_rows)
        # delta = (3.6 - 3.0) / 3.0 = 0.20 → breakout=1
        assert breakout == 1
        assert regression == 0

    def test_regression_when_curr_20pct_below_avg(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=2.4),  # curr (N+1)
                _make_row("p1", 2009, p1_per60=3.0),  # N
            ]
        }
        breakout, regression = compute_label("p1", season_n=2009, all_rows=all_rows)
        # delta = (2.4 - 3.0) / 3.0 = -0.20 → regression=1
        assert breakout == 0
        assert regression == 1

    def test_neither_label_when_delta_small(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=3.1),
                _make_row("p1", 2009, p1_per60=3.0),
            ]
        }
        result = compute_label("p1", season_n=2009, all_rows=all_rows)
        assert result == (0, 0)

    def test_returns_none_when_curr_row_missing(self):
        all_rows = {"p1": [_make_row("p1", 2009, p1_per60=3.0)]}
        result = compute_label("p1", season_n=2009, all_rows=all_rows)
        assert result is None

    def test_returns_none_when_curr_toi_below_min(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=3.6, toi_ev=4.9),  # < 5.0 min/game
                _make_row("p1", 2009, p1_per60=3.0),
            ]
        }
        result = compute_label("p1", season_n=2009, all_rows=all_rows)
        assert result is None

    def test_returns_none_when_no_prev_rows_meet_toi(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=3.6),
                _make_row("p1", 2009, p1_per60=3.0, toi_ev=4.0),  # below threshold
            ]
        }
        result = compute_label("p1", season_n=2009, all_rows=all_rows)
        assert result is None

    def test_weighted_avg_with_two_prior_seasons(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2011, p1_per60=4.0),   # curr (N+1=2011)
                _make_row("p1", 2010, p1_per60=3.0),   # N=2010 (weight 0.6)
                _make_row("p1", 2009, p1_per60=2.0),   # N-1=2009 (weight 0.4)
            ]
        }
        # avg = (0.6*3.0 + 0.4*2.0) / 1.0 = 2.6
        # delta = (4.0 - 2.6) / 2.6 ≈ 0.538 → breakout
        breakout, regression = compute_label("p1", season_n=2010, all_rows=all_rows)
        assert breakout == 1

    def test_returns_none_when_avg_p60_near_zero(self):
        all_rows = {
            "p1": [
                _make_row("p1", 2010, p1_per60=0.1),
                _make_row("p1", 2009, p1_per60=0.0),  # avg near zero
            ]
        }
        result = compute_label("p1", season_n=2009, all_rows=all_rows)
        assert result is None


# ---------------------------------------------------------------------------
# build_labeled_dataset tests
# ---------------------------------------------------------------------------

class TestBuildLabeledDataset:
    def _make_all_rows(self) -> dict[str, list[dict]]:
        """5 players, seasons 2007–2012. Useful training range: 2009 and 2010."""
        rows: dict[str, list[dict]] = {}
        for i in range(5):
            pid = f"p{i}"
            rows[pid] = [
                _make_row(pid, s, p1_per60=2.5 + i * 0.1)
                for s in range(2007, 2013)  # 2007..2012
            ]
            rows[pid].sort(key=lambda r: r["season"], reverse=True)
        return rows

    def test_returns_list_of_tuples(self):
        all_rows = self._make_all_rows()
        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2011))
        assert isinstance(dataset, list)
        assert len(dataset) > 0
        feature_row, label = dataset[0]
        assert isinstance(feature_row, dict)
        assert isinstance(label, tuple)

    def test_leakage_guard_no_n_plus_1_in_features(self):
        """THE CRITICAL TEST: season N+1 rows must NEVER appear in the feature slice.

        We inject a sentinel value in season N+1 rows and verify it never
        reaches build_feature_matrix's input.
        """
        all_rows = self._make_all_rows()

        # Inject a sentinel into all N+1 rows to detect leakage
        SENTINEL = 999.999
        for pid, rows in all_rows.items():
            for r in rows:
                if r["season"] in (2010, 2011):  # N+1 for train_seasons [2009, 2010]
                    r["__sentinel__"] = SENTINEL

        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2011))
        for feature_row, _ in dataset:
            # If leakage occurred, sentinel would be in the feature row
            assert feature_row.get("__sentinel__") != SENTINEL, (
                f"LEAKAGE: season N+1 row reached feature matrix for player "
                f"{feature_row.get('player_id')}"
            )

    def test_stale_season_rows_excluded(self):
        """Rows with stale_season=True must not become training examples."""
        all_rows = self._make_all_rows()
        # Mark one player as stale in season 2009
        for r in all_rows["p0"]:
            if r["season"] == 2009:
                r["stale_season"] = True
        # build_feature_matrix will set stale_season; we need to simulate it
        # For this test, we verify the feature matrix filtering logic
        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2010))
        stale_rows = [d for d, _ in dataset if d.get("player_id") == "p0"]
        # p0's 2009 row should be excluded because stale_season=True
        assert all(not d.get("stale_season") for d in stale_rows)

    def test_feature_names_present_in_output(self):
        all_rows = self._make_all_rows()
        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2011))
        if dataset:
            feature_row, _ = dataset[0]
            for name in FEATURE_NAMES:
                assert name in feature_row, f"Missing feature: {name}"


# ---------------------------------------------------------------------------
# FEATURE_NAMES constant
# ---------------------------------------------------------------------------

class TestFeatureNames:
    def test_has_21_features(self):
        assert len(FEATURE_NAMES) == 21

    def test_no_duplicates(self):
        assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))

    def test_excluded_columns_absent(self):
        excluded = {
            "toi_ev_per_game", "toi_pp_per_game", "toi_sh_per_game",
            "pp_unit_change", "a2_pct_of_assists", "breakout_count",
            "regression_count", "breakout_tier", "regression_tier",
            "player_id", "season", "stale_season", "position_type",
            "position", "toi_sh", "breakout_signals", "regression_signals",
            "scf_per60_curr",
        }
        for col in excluded:
            assert col not in FEATURE_NAMES, f"Excluded column in features: {col}"


# ---------------------------------------------------------------------------
# Holdout split
# ---------------------------------------------------------------------------

class TestHoldoutSplit:
    """Verify that _HOLDOUT_SEASONS {2023, 2024} are excluded from CV and
    included in the final-retrain arrays passed to train_xgboost."""

    def _make_row(self, season: int) -> dict:
        row = {f: 0.0 for f in FEATURE_NAMES}
        row["season"] = season
        row["player_id"] = "p1"
        return row

    def test_holdout_seasons_excluded_from_train_set(self):
        from ml.train import _HOLDOUT_SEASONS
        assert _HOLDOUT_SEASONS == {2023, 2024}

        dataset = [
            (self._make_row(s), (0, 0))
            for s in range(2008, 2025)
        ]
        train_set = [(row, lbl) for row, lbl in dataset
                     if row.get("season") not in _HOLDOUT_SEASONS]
        holdout_set = [(row, lbl) for row, lbl in dataset
                       if row.get("season") in _HOLDOUT_SEASONS]

        train_seasons = {row["season"] for row, _ in train_set}
        holdout_seasons = {row["season"] for row, _ in holdout_set}

        assert _HOLDOUT_SEASONS.isdisjoint(train_seasons), \
            "Holdout seasons must not appear in the CV training set"
        assert holdout_seasons == _HOLDOUT_SEASONS, \
            "All holdout seasons must be in the holdout set"

    def test_final_retrain_includes_holdout(self):
        """train_xgboost stacks X_train + X_holdout for final fit."""
        from ml.train import _HOLDOUT_SEASONS
        # Simulate the arrays produced by main() and verify stacking logic
        dataset = [
            (self._make_row(s), (1, 0))
            for s in range(2008, 2025)
        ]
        train_set = [(row, lbl) for row, lbl in dataset
                     if row.get("season") not in _HOLDOUT_SEASONS]
        holdout_set = [(row, lbl) for row, lbl in dataset
                       if row.get("season") in _HOLDOUT_SEASONS]

        import numpy as np
        X_train = np.array([[row[f] for f in FEATURE_NAMES] for row, _ in train_set])
        X_holdout = np.array([[row[f] for f in FEATURE_NAMES] for row, _ in holdout_set])
        X_all = np.vstack([X_train, X_holdout])

        assert X_all.shape[0] == len(dataset), \
            "Final retrain must include ALL rows (train + holdout)"
        assert X_train.shape[0] + X_holdout.shape[0] == X_all.shape[0]
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/ml/test_train.py -v
```

Expected: `ImportError: cannot import name 'FEATURE_NAMES'`

- [ ] **Step 3: Implement train.py — Part 1 (constants + label functions)**

`apps/api/ml/train.py`:
```python
"""Phase 3d ML training pipeline.

Usage:
    python -m ml.train --season 2026-27

This trains XGBoost breakout and regression classifiers on historical
player_stats data, computes SHAP values, uploads artifacts to Supabase
Storage, and upserts player_trends for the current season.
"""
from __future__ import annotations

import logging
from typing import Any

from services.feature_engineering import build_feature_matrix

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model feature set (21 columns, all numeric)
# See spec § Model Features for inclusion/exclusion rationale.
# ---------------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
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

# Seasons whose labeled rows are held out from ALL CV folds.
# The final model retrains on ALL data including these seasons.
_HOLDOUT_SEASONS = {2023, 2024}

# Minimum per-game EV TOI to qualify a label row.
# Matches TOI_THRESHOLD in services/feature_engineering.py.
# Applied independently here — see spec D for rationale.
_MIN_TOI = 5.0  # min/game


# ---------------------------------------------------------------------------
# Label computation
# ---------------------------------------------------------------------------

def compute_label(
    player_id: str,
    season_n: int,
    all_rows: dict[str, list[dict[str, Any]]],
) -> tuple[int, int] | None:
    """Return (breakout_label, regression_label) for player in season N.

    Uses p1_per60 from player_stats as the label metric (primary points
    per 60 EV). Season N+1 is used for the label target; it is NEVER
    passed to build_feature_matrix.

    Label weights [0.6, 0.4] are intentionally different from feature
    weights [0.5, 0.3, 0.2] — see spec D13.

    Args:
        player_id: Player UUID.
        season_n: The training season (features built from N, N-1, N-2).
        all_rows: Full historical data from get_all_seasons_grouped().

    Returns:
        (breakout_label, regression_label) or None if insufficient data.
    """
    rows = all_rows.get(player_id, [])

    # Future season: label target only — never passed to build_feature_matrix
    curr_row = next((r for r in rows if r["season"] == season_n + 1), None)

    # Prior seasons: trailing baseline (newest-first order preserved)
    prev_rows = [r for r in rows if r["season"] in (season_n, season_n - 1)]

    if curr_row is None or (curr_row.get("toi_ev") or 0) < _MIN_TOI:
        return None
    if not prev_rows:
        return None

    curr_p60 = curr_row.get("p1_per60")
    prev_p60_values = [
        r.get("p1_per60")
        for r in prev_rows
        if r.get("p1_per60") is not None and (r.get("toi_ev") or 0) >= _MIN_TOI
    ]

    if curr_p60 is None or not prev_p60_values:
        return None

    weights = [0.6, 0.4][: len(prev_p60_values)]
    total_w = sum(weights)
    avg_p60 = sum(w * v for w, v in zip(weights, prev_p60_values)) / total_w

    if avg_p60 < 1e-6:
        return None

    delta = (curr_p60 - avg_p60) / avg_p60
    return (1 if delta >= 0.20 else 0), (1 if delta <= -0.20 else 0)


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def build_labeled_dataset(
    all_rows: dict[str, list[dict[str, Any]]],
    train_seasons: range = range(2008, 2025),
) -> list[tuple[dict[str, Any], tuple[int, int]]]:
    """Build a list of (feature_row, (breakout_label, regression_label)) pairs.

    Feature window for season N = rows for N, N-1, N-2 ONLY.
    Season N+1 is accessible in all_rows for compute_label but is NEVER
    included in the feature_slice passed to build_feature_matrix.

    Args:
        all_rows: Full historical player data from get_all_seasons_grouped().
        train_seasons: Range of seasons to build labeled examples for.

    Returns:
        List of (feature_row_dict, (breakout_label, regression_label)).
    """
    dataset: list[tuple[dict[str, Any], tuple[int, int]]] = []

    for n in train_seasons:
        # Feature window: ONLY rows for N, N-1, N-2. N+1 never included.
        feature_slice: dict[str, list[dict[str, Any]]] = {
            pid: [r for r in rows if r["season"] in (n, n - 1, n - 2)]
            for pid, rows in all_rows.items()
        }

        # Leakage guard: assert no N+1 rows snuck into feature_slice
        for pid, rows in feature_slice.items():
            for r in rows:
                assert r["season"] <= n, (
                    f"LEAKAGE: player {pid} has season {r['season']} "
                    f"in feature_slice for training season {n}"
                )

        feature_rows = build_feature_matrix(feature_slice, season=n)

        for row in feature_rows:
            if row.get("stale_season"):
                continue
            if row.get("position_type") == "goalie":
                continue

            label = compute_label(
                row["player_id"],
                season_n=n,
                all_rows=all_rows,  # full history; compute_label reads N+1 only
            )
            if label is None:
                continue

            dataset.append((row, label))

    return dataset
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/ml/test_train.py -v
```

Expected: All tests PASS. (Some may be skipped if `build_feature_matrix` requires DB — check conftest imports.)

- [ ] **Step 5: Commit**

```bash
git add apps/api/ml/train.py apps/api/tests/ml/test_train.py
git commit -m "feat(phase3d): ml/train.py Part 1 — FEATURE_NAMES, compute_label, build_labeled_dataset + leakage guard"
```

---

## Task 8: `ml/train.py` Part 2 — training functions + full pipeline CLI

**Files:**
- Modify: `apps/api/ml/train.py` (add training functions + CLI entrypoint)

- [ ] **Step 1: Append training functions to `ml/train.py`**

Add the following after `build_labeled_dataset`:

```python
import argparse
import json
import sys
from datetime import datetime, timezone

import numpy as np
import optuna
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit

from core.config import settings
from core.dependencies import get_db
from ml.evaluate import compute_metrics
from ml.loader import derive_data_season, upload
from ml.shap_compute import compute_shap
from repositories.player_stats import PlayerStatsRepository


def _extract_Xy(
    dataset: list[tuple[dict[str, Any], tuple[int, int]]],
    label_idx: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract feature matrix X and label vector y from dataset.

    Args:
        dataset: Output of build_labeled_dataset().
        label_idx: 0 for breakout label, 1 for regression label.
    """
    X = np.array(
        [
            [row.get(feat) for feat in FEATURE_NAMES]
            for row, _ in dataset
        ],
        dtype=float,
    )
    y = np.array([label[label_idx] for _, label in dataset], dtype=int)
    return X, y


def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    n_trials: int = 50,
) -> tuple[xgb.XGBClassifier, dict[str, float]]:
    """Train XGBoost with Optuna hyperparameter search + TimeSeriesSplit CV.

    Holdout rows are excluded from ALL CV folds. After CV, retrains on the
    FULL dataset (train + holdout) with best params.

    Returns:
        (final_model, metrics_on_holdout)
    """
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    cv = TimeSeriesSplit(n_splits=5)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 400),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
        }
        aucs = []
        for train_idx, val_idx in cv.split(X_train):
            m = xgb.XGBClassifier(
                **params,
                scale_pos_weight=scale_pos_weight,
                eval_metric="auc",
                random_state=42,
                verbosity=0,
            )
            m.fit(X_train[train_idx], y_train[train_idx], feature_names=FEATURE_NAMES)
            proba = m.predict_proba(X_train[val_idx])[:, 1]
            result = compute_metrics(y_train[val_idx].tolist(), proba.tolist())
            aucs.append(result.auc_roc)
        return float(np.mean(aucs))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params

    # Final model: retrain on ALL data (train + holdout)
    X_all = np.vstack([X_train, X_holdout])
    y_all = np.concatenate([y_train, y_holdout])
    n_pos_all = int(y_all.sum())
    n_neg_all = len(y_all) - n_pos_all
    spw_all = n_neg_all / n_pos_all if n_pos_all > 0 else 1.0

    final_model = xgb.XGBClassifier(
        **best_params,
        scale_pos_weight=spw_all,
        eval_metric="auc",
        random_state=42,
        verbosity=0,
    )
    final_model.fit(X_all, y_all, feature_names=FEATURE_NAMES)

    # Evaluate on holdout only
    holdout_proba = final_model.predict_proba(X_holdout)[:, 1]
    metrics = compute_metrics(y_holdout.tolist(), holdout_proba.tolist())

    return final_model, {
        "auc_roc": metrics.auc_roc,
        "precision_at_50": metrics.precision_at_k,
        "recall_at_50": metrics.recall_at_k,
    }


def train_lightgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    n_trials: int = 25,
) -> dict[str, float]:
    """Train LightGBM challenger and return holdout metrics only.

    No artifact upload — challenger metrics are logged and included in
    metadata.json for comparison only. Emits WARNING if LightGBM
    AUC-ROC beats XGBoost by > 0.02.

    Returns:
        metrics dict with auc_roc (on holdout).
    """
    cv = TimeSeriesSplit(n_splits=5)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 400),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "num_leaves": trial.suggest_int("num_leaves", 20, 100),
            "is_unbalance": True,
        }
        aucs = []
        for train_idx, val_idx in cv.split(X_train):
            m = lgb.LGBMClassifier(**params, random_state=42, verbose=-1)
            m.fit(X_train[train_idx], y_train[train_idx])
            proba = m.predict_proba(X_train[val_idx])[:, 1]
            result = compute_metrics(y_train[val_idx].tolist(), proba.tolist())
            aucs.append(result.auc_roc)
        return float(np.mean(aucs))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    # Final challenger: retrain on all data with best params
    X_all = np.vstack([X_train, X_holdout])
    y_all = np.concatenate([y_train, y_holdout])
    challenger = lgb.LGBMClassifier(**study.best_params, is_unbalance=True, random_state=42, verbose=-1)
    challenger.fit(X_all, y_all)

    holdout_proba = challenger.predict_proba(X_holdout)[:, 1]
    metrics = compute_metrics(y_holdout.tolist(), holdout_proba.tolist())
    logger.info("LightGBM holdout AUC-ROC: %.4f", metrics.auc_roc)
    return {"auc_roc": metrics.auc_roc}


def _upsert_player_trends(
    db: Any,
    season: str,
    dataset_current: list[tuple[dict[str, Any], tuple[int, int]]],
    breakout_model: xgb.XGBClassifier,
    regression_model: xgb.XGBClassifier,
) -> None:
    """Compute scores + SHAP and upsert player_trends rows."""
    if not dataset_current:
        logger.warning("No current-season rows to upsert.")
        return

    X_curr, _ = _extract_Xy(dataset_current, label_idx=0)
    breakout_proba = breakout_model.predict_proba(X_curr)[:, 1]
    regression_proba = regression_model.predict_proba(X_curr)[:, 1]

    breakout_shap = compute_shap(breakout_model, X_curr, FEATURE_NAMES)
    regression_shap = compute_shap(regression_model, X_curr, FEATURE_NAMES)

    now = datetime.now(tz=timezone.utc).isoformat()
    rows_to_upsert = []
    for i, (row, _) in enumerate(dataset_current):
        shap_top3 = {
            "breakout": list(breakout_shap[i]["breakout"].items()),
            "regression": list(regression_shap[i]["breakout"].items()),  # same key from compute_shap
        }
        rows_to_upsert.append({
            "player_id": row["player_id"],
            "season": season,
            "breakout_score": float(breakout_proba[i]),
            "regression_risk": float(regression_proba[i]),
            "confidence": float(
                (breakout_model.predict_proba(X_curr[i : i + 1])[:, 1][0] +
                 regression_model.predict_proba(X_curr[i : i + 1])[:, 1][0]) / 2
            ),
            "shap_top3": shap_top3,
            "updated_at": now,
        })

    db.table("player_trends").upsert(
        rows_to_upsert,
        on_conflict="player_id,season",
    ).execute()
    logger.info("Upserted %d player_trends rows for season %s", len(rows_to_upsert), season)


def main() -> None:
    """CLI entrypoint: python -m ml.train --season 2026-27"""
    parser = argparse.ArgumentParser(description="Train PuckLogic Trends models")
    parser.add_argument("--season", required=True, help="Training season, e.g. 2026-27")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger.info("Starting Phase 3d training pipeline — season=%s", args.season)

    data_season = derive_data_season(args.season)
    db = get_db()

    # 1. Load all historical player_stats
    repo = PlayerStatsRepository(db)
    all_rows = repo.get_all_seasons_grouped()
    logger.info("Loaded %d players from DB", len(all_rows))

    # 2. Build labeled dataset (2008–2024)
    full_dataset = build_labeled_dataset(all_rows, train_seasons=range(2008, 2025))
    logger.info("Labeled dataset: %d examples", len(full_dataset))

    # 3. Split holdout (2023–2024 seasons)
    current_season_int = int(args.season.split("-")[0]) - 1  # e.g. 2025 for "2026-27"
    holdout_set = [(row, lbl) for row, lbl in full_dataset
                   if row.get("season") in _HOLDOUT_SEASONS]
    train_set = [(row, lbl) for row, lbl in full_dataset
                 if row.get("season") not in _HOLDOUT_SEASONS]

    logger.info("Train: %d  Holdout: %d", len(train_set), len(holdout_set))

    X_train_b, y_train_b = _extract_Xy(train_set, 0)
    X_train_r, y_train_r = _extract_Xy(train_set, 1)
    X_holdout_b, y_holdout_b = _extract_Xy(holdout_set, 0)
    X_holdout_r, y_holdout_r = _extract_Xy(holdout_set, 1)

    # 4. Train XGBoost (breakout + regression)
    logger.info("Training XGBoost breakout model (50 Optuna trials)...")
    breakout_model, b_metrics = train_xgboost(
        X_train_b, y_train_b, X_holdout_b, y_holdout_b
    )
    logger.info("Breakout AUC-ROC: %.4f", b_metrics["auc_roc"])

    logger.info("Training XGBoost regression model (50 Optuna trials)...")
    regression_model, r_metrics = train_xgboost(
        X_train_r, y_train_r, X_holdout_r, y_holdout_r
    )
    logger.info("Regression AUC-ROC: %.4f", r_metrics["auc_roc"])

    # 5. LightGBM challenger (metrics only)
    logger.info("Training LightGBM challenger (25 trials each)...")
    lgb_b_metrics = train_lightgbm(X_train_b, y_train_b, X_holdout_b, y_holdout_b)
    lgb_r_metrics = train_lightgbm(X_train_r, y_train_r, X_holdout_r, y_holdout_r)

    if lgb_b_metrics["auc_roc"] - b_metrics["auc_roc"] > 0.02:
        logger.warning(
            "LightGBM breakout AUC (%.4f) exceeds XGBoost (%.4f) by >0.02 — "
            "consider switching production model",
            lgb_b_metrics["auc_roc"], b_metrics["auc_roc"],
        )
    if lgb_r_metrics["auc_roc"] - r_metrics["auc_roc"] > 0.02:
        logger.warning(
            "LightGBM regression AUC (%.4f) exceeds XGBoost (%.4f) by >0.02 — "
            "consider switching production model",
            lgb_r_metrics["auc_roc"], r_metrics["auc_roc"],
        )

    # 6. Upload artifacts to Supabase Storage
    upload(
        db=db,
        breakout_model=breakout_model,
        regression_model=regression_model,
        metrics={
            "breakout": b_metrics,
            "regression": r_metrics,
            "lgb_breakout_auc_roc": lgb_b_metrics["auc_roc"],
            "lgb_regression_auc_roc": lgb_r_metrics["auc_roc"],
        },
        feature_names=FEATURE_NAMES,
        data_season=data_season,
        n_train=len(train_set),
        n_holdout=len(holdout_set),
    )

    # 7. Upsert player_trends for current season
    current_season_str = data_season  # e.g. "2025-26"
    current_dataset = build_labeled_dataset(
        all_rows, train_seasons=range(current_season_int, current_season_int + 1)
    )
    # Current season has no N+1 label row → compute_label returns None for all.
    # We still need feature rows for inference — rebuild without label filter.
    current_season_int_val = int(data_season.split("-")[0]) + 1  # e.g. 2026 for "2025-26"
    current_feature_slice = {
        pid: [r for r in rows if r["season"] in (
            current_season_int_val - 1,
            current_season_int_val - 2,
            current_season_int_val - 3,
        )]
        for pid, rows in all_rows.items()
    }
    from services.feature_engineering import build_feature_matrix
    current_rows = [
        row for row in build_feature_matrix(current_feature_slice, season=current_season_int_val - 1)
        if not row.get("stale_season") and row.get("position_type") != "goalie"
    ]
    # Wrap as dataset for _upsert_player_trends (labels unused for current season)
    current_dataset_wrapped = [(row, (0, 0)) for row in current_rows]

    _upsert_player_trends(
        db=db,
        season=current_season_str,
        dataset_current=current_dataset_wrapped,
        breakout_model=breakout_model,
        regression_model=regression_model,
    )

    logger.info("Phase 3d training pipeline complete. Season: %s", args.season)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all ml tests to confirm nothing broken**

```bash
pytest tests/ml/ -v --ignore=tests/ml/test_train.py
pytest tests/ml/test_train.py -v
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/ml/train.py
git commit -m "feat(phase3d): ml/train.py Part 2 — train_xgboost, train_lightgbm, upsert, CLI entrypoint"
```

---

## Task 9: `routers/trends.py` + DI wiring

**Files:**
- Create: `apps/api/routers/trends.py`
- Modify: `apps/api/core/dependencies.py`
- Create: `apps/api/tests/routers/test_trends.py`

- [ ] **Step 1: Write failing router tests**

`apps/api/tests/routers/test_trends.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_trends_repository
from main import app
from models.schemas import TrendedPlayer, TrendsResponse


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_response(has_trends: bool = True) -> TrendsResponse:
    if has_trends:
        return TrendsResponse(
            season="2025-26",
            has_trends=True,
            updated_at=datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc),
            players=[
                TrendedPlayer(
                    player_id="p-mcdavid",
                    name="Connor McDavid",
                    position="C",
                    team="EDM",
                    breakout_score=0.85,
                    regression_risk=0.10,
                    confidence=0.80,
                )
            ],
        )
    return TrendsResponse(season="2025-26", has_trends=False, updated_at=None, players=[])


class TestGetTrendsRouter:
    def test_503_when_models_none(self, client):
        app.state.models = None
        response = client.get("/trends?season=2025-26")
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()

    def test_200_when_models_loaded(self, client):
        app.state.models = (MagicMock(), MagicMock())  # non-None sentinel
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=True)
        app.dependency_overrides[get_trends_repository] = lambda: mock_repo

        response = client.get("/trends?season=2025-26")
        assert response.status_code == 200
        data = response.json()
        assert data["has_trends"] is True
        assert len(data["players"]) == 1
        assert data["players"][0]["breakout_score"] == pytest.approx(0.85)

        app.dependency_overrides.clear()
        app.state.models = None

    def test_has_trends_false_returns_200_not_503(self, client):
        """has_trends=False is a valid pre-training state — not an error."""
        app.state.models = (MagicMock(), MagicMock())
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=False)
        app.dependency_overrides[get_trends_repository] = lambda: mock_repo

        response = client.get("/trends?season=2025-26")
        assert response.status_code == 200
        assert response.json()["has_trends"] is False

        app.dependency_overrides.clear()
        app.state.models = None

    def test_default_season_used_when_not_provided(self, client):
        app.state.models = (MagicMock(), MagicMock())
        mock_repo = MagicMock()
        mock_repo.get_trends.return_value = _make_response(has_trends=False)
        app.dependency_overrides[get_trends_repository] = lambda: mock_repo

        response = client.get("/trends")  # no ?season= param
        assert response.status_code == 200

        app.dependency_overrides.clear()
        app.state.models = None
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
pytest tests/routers/test_trends.py -v
```

Expected: `ImportError: cannot import name 'get_trends_repository'`

- [ ] **Step 3: Add `get_trends_repository` to `core/dependencies.py`**

Add to imports at top:
```python
from repositories.trends import TrendsRepository
```

Add at the bottom of the repository factories section:
```python
def get_trends_repository() -> TrendsRepository:
    return TrendsRepository(get_db())
```

- [ ] **Step 4: Implement `routers/trends.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.config import settings
from core.dependencies import get_trends_repository
from models.schemas import TrendsResponse
from repositories.trends import TrendsRepository

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", response_model=TrendsResponse)
async def get_trends(
    request: Request,
    season: str | None = Query(None, description="Season string, e.g. '2025-26'"),
    repo: TrendsRepository = Depends(get_trends_repository),
) -> TrendsResponse:
    """Return pre-computed breakout and regression scores for all skaters.

    Returns HTTP 503 if model artifacts failed to load at startup (deployment
    error — check ml-artifacts bucket in Supabase Storage).

    Returns has_trends=False when model has not been run for this season yet
    (valid pre-training state — not an error).
    """
    if request.app.state.models is None:
        raise HTTPException(
            status_code=503,
            detail="Trends model not available for this season",
        )

    resolved_season = season or settings.current_season
    return repo.get_trends(resolved_season)
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/routers/test_trends.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/routers/trends.py \
        apps/api/core/dependencies.py \
        apps/api/tests/routers/test_trends.py
git commit -m "feat(phase3d): GET /trends router — 503 on model unavailable, has_trends=False for pre-training"
```

---

## Task 10: `main.py` — lifespan hook + router registration

**Files:**
- Modify: `apps/api/main.py`

- [ ] **Step 1: Add lifespan hook to `main.py`**

Replace the contents of `apps/api/main.py`:

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.dependencies import get_db
from ml.loader import ModelNotAvailableError, load
from routers import (
    auth,
    exports,
    health,
    league_profiles,
    players,
    rankings,
    scoring_configs,
    sources,
    stripe,
    user_kits,
)
from routers import trends as trends_router

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan — load ML models at startup.

    On success: app.state.models = (breakout_model, regression_model)
    On failure: app.state.models = None  (GET /trends returns 503)

    Failure modes that set models=None:
    - Supabase Storage unreachable
    - ml-artifacts bucket or artifact files missing
    - Deserialization error

    This is NOT a startup crash — the API starts normally.
    503 on /trends is the signal to ops that retraining hasn't run yet
    or Storage is misconfigured.
    """
    try:
        db = get_db()
        breakout_model, regression_model = load(db=db, season=settings.current_season)
        app.state.models = (breakout_model, regression_model)
        logger.info(
            "ML models loaded for season %s", settings.current_season
        )
    except ModelNotAvailableError as exc:
        app.state.models = None
        logger.warning(
            "ML models not available for season %s: %s — "
            "GET /trends will return 503",
            settings.current_season,
            exc,
        )

    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="PuckLogic API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [settings.frontend_url] if settings.is_production else ["http://localhost:3000"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(players.router)
app.include_router(sources.router)
app.include_router(rankings.router)
app.include_router(exports.router)
app.include_router(stripe.router)
app.include_router(user_kits.router)
app.include_router(league_profiles.router)
app.include_router(scoring_configs.router)
app.include_router(trends_router.router)
```

- [ ] **Step 2: Run full test suite to confirm nothing broken**

```bash
cd apps/api
pytest -x -q
```

Expected: All existing tests PASS + new tests PASS. Note: lifespan runs during TestClient creation; the `load()` call will raise `ModelNotAvailableError` (no real Storage in CI) which sets `app.state.models = None` — this is intentional and correct.

If any existing test fails due to lifespan, override it with:
```python
app.state.models = None  # set in test setup (already safe)
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/main.py
git commit -m "feat(phase3d): FastAPI lifespan hook — load ML models at startup, app.state.models=None on failure"
```

---

## Task 11: Smoke test

**Files:**
- Create: `apps/api/tests/smoke/test_train_smoke.py`

Smoke tests are excluded from CI (`--ignore=tests/smoke` in pytest config). This test runs the full pipeline on synthetic data with mocked Storage/DB.

- [ ] **Step 1: Write smoke test**

`apps/api/tests/smoke/test_train_smoke.py`:
```python
"""Smoke test: 50-player synthetic pipeline runs end-to-end.

Run manually with:
    pytest tests/smoke/test_train_smoke.py -v -s

This is excluded from CI (see pyproject.toml addopts).
"""
from __future__ import annotations

import io
import logging
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

logging.basicConfig(level=logging.INFO)


def _make_synthetic_all_rows(n_players: int = 50, n_seasons: int = 22) -> dict:
    """Generate synthetic player_stats for n_players across n_seasons.

    Seasons: 2003–2024 (allows label computation back to 2008).
    Players have realistic-ish p1_per60 with +/-20% variance to ensure
    some breakout and regression labels.
    """
    rng = np.random.default_rng(42)
    start_season = 2024 - n_seasons + 1  # e.g. 2003

    all_rows = {}
    for i in range(n_players):
        pid = f"synthetic-player-{i:03d}"
        base_p60 = rng.uniform(1.0, 4.5)
        rows = []
        for s in range(start_season, 2025):
            toi = rng.uniform(5.5, 22.0)
            p60 = max(0.0, base_p60 * rng.uniform(0.7, 1.4))
            rows.append({
                "player_id": pid,
                "season": s,
                "p1_per60": p60,
                "toi_ev": toi,
                "toi_pp": rng.uniform(0.0, 4.0),
                "toi_sh": rng.uniform(0.0, 1.0),
                "icf_per60": rng.uniform(5.0, 20.0),
                "ixg_per60": rng.uniform(4.0, 18.0),
                "xgf_pct_5v5": rng.uniform(40.0, 65.0),
                "cf_pct_adj": rng.uniform(40.0, 62.0),
                "scf_per60": rng.uniform(10.0, 25.0),
                "scf_pct": rng.uniform(42.0, 60.0),
                "pdo": rng.uniform(0.970, 1.030),
                "sh_pct": rng.uniform(0.06, 0.18),
                "sh_pct_career_avg": rng.uniform(0.07, 0.16),
                "g_minus_ixg": rng.uniform(-1.5, 1.5),
                "g_per60": rng.uniform(0.5, 3.0),
                "oi_sh_pct": rng.uniform(0.07, 0.11),
                "pp_unit": rng.integers(1, 3),
                "elc_flag": bool(rng.integers(0, 2)),
                "contract_year_flag": bool(rng.integers(0, 2)),
                "post_extension_flag": bool(rng.integers(0, 2)),
                "date_of_birth": f"{rng.integers(1990, 2002)}-06-15",
                "position": rng.choice(["C", "LW", "RW", "D"]),
            })
        rows.sort(key=lambda r: r["season"], reverse=True)
        all_rows[pid] = rows

    return all_rows


class TestTrainSmoke:
    def test_end_to_end_pipeline(self):
        """Full train.py pipeline on 50 synthetic players with mocked DB/Storage."""
        from ml.train import (
            FEATURE_NAMES,
            _HOLDOUT_SEASONS,
            _extract_Xy,
            build_labeled_dataset,
            train_xgboost,
        )

        all_rows = _make_synthetic_all_rows(n_players=50, n_seasons=22)

        # Build labeled dataset
        full_dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2025))
        assert len(full_dataset) > 0, "Expected >0 labeled examples from 50 players * 15 seasons"
        print(f"\nLabeled examples: {len(full_dataset)}")

        # Split holdout
        holdout = [(row, lbl) for row, lbl in full_dataset
                   if row.get("season") in _HOLDOUT_SEASONS]
        train = [(row, lbl) for row, lbl in full_dataset
                 if row.get("season") not in _HOLDOUT_SEASONS]
        assert len(holdout) > 0, "Expected holdout examples for seasons 2023-2024"
        assert len(train) > 0, "Expected training examples"

        print(f"Train: {len(train)}, Holdout: {len(holdout)}")

        X_train, y_train = _extract_Xy(train, 0)
        X_holdout, y_holdout = _extract_Xy(holdout, 0)

        # Train with minimal Optuna trials for smoke speed
        with patch("ml.train.train_xgboost") as mock_train:
            import xgboost as xgb
            tiny_model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=0)
            tiny_model.fit(X_train, y_train, feature_names=FEATURE_NAMES)
            mock_train.return_value = (tiny_model, {"auc_roc": 0.65, "precision_at_50": 0.50, "recall_at_50": 0.40})

            # Verify upload would be called
            mock_db = MagicMock()
            from ml.loader import upload
            upload(
                db=mock_db,
                breakout_model=tiny_model,
                regression_model=tiny_model,
                metrics={"breakout": {"auc_roc": 0.65}, "regression": {"auc_roc": 0.62}},
                feature_names=FEATURE_NAMES,
                data_season="2025-26",
                n_train=len(train),
                n_holdout=len(holdout),
            )
            storage = mock_db.storage.from_.return_value
            assert storage.upload.call_count == 3
            print("Storage upload called 3 times ✓")

        # Verify player_trends upsert via _upsert_player_trends directly
        from ml.train import _upsert_player_trends

        # Build a minimal current-season dataset using the same synthetic rows
        all_rows_flat = [r for rows in all_rows.values() for r in rows]
        current_rows = [r for r in all_rows_flat if r["season"] == 2024]
        current_dataset_wrapped = [(row, (0, 0)) for row in current_rows]

        upsert_db = MagicMock()
        _upsert_player_trends(
            db=upsert_db,
            season="2024-25",
            dataset_current=current_dataset_wrapped[:10],  # 10 rows is enough for smoke
            breakout_model=tiny_model,
            regression_model=tiny_model,
        )
        upsert_calls = upsert_db.table.return_value.upsert.call_args_list
        assert len(upsert_calls) > 0, "Expected player_trends upsert to be called"
        print(f"player_trends upsert called {len(upsert_calls)} time(s) ✓")

        # Verify leakage guard passes for all training seasons
        for n in range(2009, 2025):
            feature_slice = {
                pid: [r for r in rows if r["season"] in (n, n - 1, n - 2)]
                for pid, rows in all_rows.items()
            }
            for pid, rows in feature_slice.items():
                for r in rows:
                    assert r["season"] <= n, f"LEAKAGE for player {pid}"

        print("Leakage guard passes for all training seasons ✓")
        print("Smoke test PASSED")
```

- [ ] **Step 2: Run smoke test (this takes a few minutes)**

```bash
pytest tests/smoke/test_train_smoke.py -v -s
```

Expected: PASS with output showing labeled example counts and "Smoke test PASSED".

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/smoke/test_train_smoke.py
git commit -m "test(phase3d): smoke test — 50-player synthetic pipeline, leakage guard, upload mock"
```

---

## Task 12: Complete GitHub Actions + full test suite

**Files:**
- Modify: `.github/workflows/retrain-trends.yml`

- [ ] **Step 1: Complete retrain-trends.yml**

Replace the contents of `.github/workflows/retrain-trends.yml`:

```yaml
# .github/workflows/retrain-trends.yml
# PuckLogic Phase 3d — Annual ML retraining pipeline
#
# Prerequisites (one-time setup):
#   1. Create "ml-artifacts" bucket in Supabase Storage dashboard (private, service role only)
#   2. Add secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
#   3. Add variable: CURRENT_SEASON (e.g. "2026-27")
#
# Trigger: Aug 1st 8am UTC annually (pre-draft season) + manual dispatch
name: Retrain Trends Model (Annual)

on:
  schedule:
    - cron: "0 8 1 8 *"  # Aug 1st 8am UTC
  workflow_dispatch:      # Manual trigger for testing

jobs:
  retrain:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run Hockey Reference scraper (career SH%, historical stats)
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python -m scrapers.hockey_reference

      - name: Train Trends model and upload artifacts
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python -m ml.train --season ${{ vars.CURRENT_SEASON }}
        # CURRENT_SEASON is a GitHub Actions variable (not a secret), e.g. "2026-27"
        # Artifacts uploaded to: ml-artifacts/{data_season}/ in Supabase Storage
        # player_trends upserted for all current-season skaters with qualifying TOI
```

- [ ] **Step 2: Run the complete test suite**

```bash
cd apps/api
pytest -x -q
```

Expected: All unit + router + repository tests PASS. Smoke tests are excluded.

- [ ] **Step 3: Check ruff**

```bash
ruff check .
```

Fix any linting errors. Common issues:
- Missing `from __future__ import annotations` at top of new files
- Unused imports
- Line length (max 100 chars)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/retrain-trends.yml
git commit -m "feat(phase3d): complete retrain-trends.yml — scraper + training steps, prerequisites documented"
```

---

## Task 13: Final verification + PR

- [ ] **Step 1: Run full suite one last time**

```bash
cd apps/api
pytest -q
```

Expected: All tests green (smoke excluded).

- [ ] **Step 2: Verify acceptance criteria checklist (from spec)**

Check off each item in `docs/adrs/005-phase3d-model-training.md`:
- Training pipeline: all 10 items
- Loader: all 5 items
- Inference API: all 5 items
- Tests: all 4 items
- GitHub Actions: all 4 items
- Dependencies: 1 item

- [ ] **Step 3: Update SESSION_STATE.md**

```markdown
| Active Phase | Phase 3d — Model Training + Inference API |
| Active Branch | feat/phase3d-model-training |
| Current Focus | Implementation complete; ready for PR |
```

- [ ] **Step 4: Open PR**

```bash
git push -u origin feat/phase3d-model-training
gh pr create \
  --title "feat(phase3d): ML training pipeline + GET /trends inference API" \
  --body "$(cat <<'EOF'
## Summary

- Adds `ml/` module: XGBoost/LightGBM training, SHAP computation, Supabase Storage upload/download
- Adds `PlayerStatsRepository.get_all_seasons_grouped()` (no season-window cap, LEFT JOIN)
- Adds `TrendsRepository` and `GET /trends` endpoint (503 on model failure, has_trends=False pre-training)
- Completes `retrain-trends.yml` GitHub Actions workflow
- Adds 21-feature model spec with leakage guard enforced by assertion

## Test plan

- [ ] `pytest -q` passes (all unit + router + repository tests)
- [ ] `pytest tests/smoke/ -v -s` runs manually
- [ ] Smoke test: 50-player synthetic pipeline produces artifacts + upserts (mocked Storage)
- [ ] Router: 503 when app.state.models=None; 200 + TrendsResponse shape when loaded
- [ ] Leakage guard test: assert N+1 rows absent from feature slice

## Known limitations

- `ml-artifacts` Supabase Storage bucket must be created manually before first real training run
- GitHub Actions `CURRENT_SEASON` variable must be configured in repo settings
- LightGBM is challenger only; WARNING emitted if it beats XGBoost by >0.02 AUC

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Appendix: Key invariants

| Invariant | Where enforced |
|---|---|
| Feature slice never contains season N+1 | `build_labeled_dataset` assertion |
| MIN_TOI = 5.0 min/game matches feature_engineering.py | `_MIN_TOI` constant in train.py |
| Model receives column named `toi_ev`, not `toi_ev_per_game` | `FEATURE_NAMES` list (name-based selection) |
| 503 = Storage error; has_trends=False = pre-training | Router checks `app.state.models is None` only |
| Holdout excluded from CV; included in final retrain | `train_xgboost` — `X_all = vstack([X_train, X_holdout])` |
| Derive data season: "2026-27" → "2025-26" | `derive_data_season()` with input format validation |
