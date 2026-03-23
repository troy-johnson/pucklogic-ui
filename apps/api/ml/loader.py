from __future__ import annotations

import io
import json
import logging
import os
from datetime import UTC, datetime
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


def _download_model(db: Client, data_season: str, filename: str) -> xgb.XGBClassifier:
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


def load(db: Client, season: str) -> tuple[xgb.XGBClassifier, xgb.XGBClassifier]:
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
    db: Client,
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
        metrics: Dict with "breakout", "regression", and optional LGB AUC keys.
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
        "trained_at": datetime.now(tz=UTC).isoformat(),
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
