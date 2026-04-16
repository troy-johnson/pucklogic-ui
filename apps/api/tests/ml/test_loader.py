from __future__ import annotations

import io
import os
from unittest.mock import patch

import joblib
import pytest

from ml.loader import ModelNotAvailableError, derive_data_season, load, upload
from tests.ml.conftest import FEATURE_NAMES_21 as FEATURE_NAMES

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
        mock_db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        regression_model = tiny_model

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

        storage_bucket = mock_db.storage.from_.return_value
        assert storage_bucket.upload.call_count == 3

    def test_upload_uses_correct_paths(self, tiny_model):
        mock_db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
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
    def test_raises_when_storage_fails(self, tmp_path):
        mock_db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        mock_db.storage.from_.return_value.download.side_effect = Exception("not found")

        with (
            patch.dict(os.environ, {"PUCKLOGIC_NO_DEV_CACHE": "1"}),
            patch("ml.loader._DEV_CACHE_DIR", tmp_path),
            pytest.raises(ModelNotAvailableError),
        ):
            load(db=mock_db, season="2026-27")

    def test_returns_tuple_of_models_on_success(self, tiny_model, tmp_path):
        """Mock the Storage download to return serialized tiny_model bytes."""
        buf = io.BytesIO()
        joblib.dump(tiny_model, buf)
        model_bytes = buf.getvalue()

        mock_db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        mock_db.storage.from_.return_value.download.return_value = model_bytes

        with patch.dict(os.environ, {"PUCKLOGIC_NO_DEV_CACHE": "1"}):
            breakout, regression = load(db=mock_db, season="2026-27")

        assert breakout is not None
        assert regression is not None

    def test_dev_cache_skips_storage_download(self, tiny_model, tmp_path):
        """When cache file exists and PUCKLOGIC_NO_DEV_CACHE is not set, Storage is NOT called."""
        data_season = "2025-26"

        cache_dir = tmp_path / data_season
        cache_dir.mkdir(parents=True)
        for filename in ("breakout_model.joblib", "regression_model.joblib"):
            joblib.dump(tiny_model, cache_dir / filename)

        mock_db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("ml.loader._DEV_CACHE_DIR", tmp_path),
        ):
            os.environ.pop("PUCKLOGIC_NO_DEV_CACHE", None)
            breakout, regression = load(db=mock_db, season="2026-27")

        mock_db.storage.from_.return_value.download.assert_not_called()
        assert breakout is not None
        assert regression is not None
