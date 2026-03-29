"""Phase 3d ML training pipeline.

Usage:
    python -m ml.train --season 2026-27

This trains XGBoost breakout and regression classifiers on historical
player_stats data, computes SHAP values, uploads artifacts to Supabase
Storage, and upserts player_trends for the current season.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb
import numpy as np
import optuna
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit

from core.config import settings  # noqa: F401 — imported for side effects (env validation)
from core.dependencies import get_db
from ml.evaluate import compute_metrics
from ml.loader import derive_data_season, upload
from ml.shap_compute import compute_shap
from repositories.player_stats import PlayerStatsRepository
from services.feature_engineering import build_feature_matrix

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model feature set (23 columns, all numeric)
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
    "hits_per60",  # Marcel-weighted physical rate (Tier 3)
    "blocks_per60",  # Marcel-weighted physical rate (Tier 3)
]

# Seasons whose labeled rows are held out from ALL CV folds.
# The final model retrains on ALL data including these seasons.
_HOLDOUT_SEASONS = {2023, 2024}

# Minimum per-game EV TOI to qualify a label row.
# Matches TOI_THRESHOLD in services/feature_engineering.py.
# Applied independently here — not delegated to build_feature_matrix.
_MIN_TOI = 5.0  # min/game


def _season_to_year_int(season: Any) -> int | None:
    """Normalize season values to integer end-year.

    Supports:
    - int season years (e.g. 2025)
    - season labels (e.g. "2024-25" -> 2025)
    Returns None when parsing fails.
    """
    if isinstance(season, int):
        return season
    if isinstance(season, str):
        if "-" in season:
            head = season.split("-")[0]
            if head.isdigit():
                return int(head) + 1
        if season.isdigit():
            return int(season)
    return None


def _normalize_all_rows_seasons(
    all_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Return all_rows with row['season'] normalized to integer end-year.

    Rows with unparseable season values are skipped.
    """
    normalized: dict[str, list[dict[str, Any]]] = {}
    for player_id, rows in all_rows.items():
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            season_int = _season_to_year_int(row.get("season"))
            if season_int is None:
                continue
            normalized_rows.append({**row, "season": season_int})
        if normalized_rows:
            normalized_rows.sort(key=lambda r: r["season"], reverse=True)
            normalized[player_id] = normalized_rows
    return normalized


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


# ---------------------------------------------------------------------------
# Feature / label extraction
# ---------------------------------------------------------------------------


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
        [[row.get(feat) for feat in FEATURE_NAMES] for row, _ in dataset],
        dtype=float,
    )
    y = np.array([label[label_idx] for _, label in dataset], dtype=int)
    return X, y


# ---------------------------------------------------------------------------
# XGBoost training
# ---------------------------------------------------------------------------


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
            m.fit(X_train[train_idx], y_train[train_idx])
            proba = m.predict_proba(X_train[val_idx])[:, 1]
            result = compute_metrics(y_train[val_idx].tolist(), proba.tolist())
            aucs.append(result.auc_roc)
        return float(np.mean(aucs))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    best_params = study.best_params

    # Pre-retrain evaluation: train on X_train only to obtain valid holdout metrics.
    # The final artifact is trained on ALL data (train + holdout); evaluating it
    # on holdout would report inflated performance because the model has seen
    # those rows. This intermediate model is discarded after evaluation.
    pre_retrain_model = xgb.XGBClassifier(
        **best_params,
        scale_pos_weight=scale_pos_weight,
        eval_metric="auc",
        random_state=42,
        verbosity=0,
    )
    pre_retrain_model.fit(X_train, y_train)
    holdout_proba = pre_retrain_model.predict_proba(X_holdout)[:, 1]
    metrics = compute_metrics(y_holdout.tolist(), holdout_proba.tolist())

    # Final model: retrain on ALL data (train + holdout) for the production artifact.
    # Reported metrics above are from pre_retrain_model — valid holdout estimates.
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
    final_model.fit(X_all, y_all)

    return final_model, {
        "auc_roc": metrics.auc_roc,
        "precision_at_50": metrics.precision_at_50,
        "recall_at_50": metrics.recall_at_50,
    }


# ---------------------------------------------------------------------------
# LightGBM challenger
# ---------------------------------------------------------------------------


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

    # Pre-retrain evaluation: same pattern as train_xgboost — evaluate on holdout
    # before retraining on all data so metrics reflect true out-of-sample performance.
    pre_retrain_challenger = lgb.LGBMClassifier(
        **study.best_params, is_unbalance=True, random_state=42, verbose=-1
    )
    pre_retrain_challenger.fit(X_train, y_train)
    holdout_proba = pre_retrain_challenger.predict_proba(X_holdout)[:, 1]
    metrics = compute_metrics(y_holdout.tolist(), holdout_proba.tolist())
    logger.info("LightGBM holdout AUC-ROC: %.4f", metrics.auc_roc)

    # Final challenger: retrain on all data with best params (discarded after comparison).
    X_all = np.vstack([X_train, X_holdout])
    y_all = np.concatenate([y_train, y_holdout])
    challenger = lgb.LGBMClassifier(
        **study.best_params, is_unbalance=True, random_state=42, verbose=-1
    )
    challenger.fit(X_all, y_all)

    return {"auc_roc": metrics.auc_roc}


# ---------------------------------------------------------------------------
# player_trends upsert
# ---------------------------------------------------------------------------


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

    breakout_shap = compute_shap(breakout_model, X_curr, FEATURE_NAMES, label="breakout")
    regression_shap = compute_shap(regression_model, X_curr, FEATURE_NAMES, label="regression")

    now = datetime.now(tz=UTC).isoformat()
    rows_to_upsert = []
    for i, (row, _) in enumerate(dataset_current):
        shap_top3 = {
            "breakout": list(breakout_shap[i]["breakout"].items()),
            "regression": list(regression_shap[i]["regression"].items()),
        }
        confidence = float((breakout_proba[i] + regression_proba[i]) / 2)
        rows_to_upsert.append(
            {
                "player_id": row["player_id"],
                "season": season,
                "breakout_score": float(breakout_proba[i]),
                "regression_risk": float(regression_proba[i]),
                "confidence": confidence,
                "shap_top3": shap_top3,
                "updated_at": now,
            }
        )

    db.table("player_trends").upsert(
        rows_to_upsert,
        on_conflict="player_id,season",
    ).execute()
    logger.info("Upserted %d player_trends rows for season %s", len(rows_to_upsert), season)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


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
    all_rows = _normalize_all_rows_seasons(repo.get_all_seasons_grouped())
    logger.info("Loaded %d players from DB", len(all_rows))

    # 2. Build labeled dataset (2008–2024)
    full_dataset = build_labeled_dataset(all_rows, train_seasons=range(2008, 2025))
    logger.info("Labeled dataset: %d examples", len(full_dataset))

    # 3. Split holdout (2023–2024 seasons)
    holdout_set = [(row, lbl) for row, lbl in full_dataset if row.get("season") in _HOLDOUT_SEASONS]
    train_set = [
        (row, lbl) for row, lbl in full_dataset if row.get("season") not in _HOLDOUT_SEASONS
    ]
    logger.info("Train: %d  Holdout: %d", len(train_set), len(holdout_set))

    X_train_b, y_train_b = _extract_Xy(train_set, 0)
    X_train_r, y_train_r = _extract_Xy(train_set, 1)
    X_holdout_b, y_holdout_b = _extract_Xy(holdout_set, 0)
    X_holdout_r, y_holdout_r = _extract_Xy(holdout_set, 1)

    # 4. Train XGBoost (breakout + regression)
    logger.info("Training XGBoost breakout model (50 Optuna trials)...")
    breakout_model, b_metrics = train_xgboost(X_train_b, y_train_b, X_holdout_b, y_holdout_b)
    logger.info("Breakout AUC-ROC: %.4f", b_metrics["auc_roc"])

    logger.info("Training XGBoost regression model (50 Optuna trials)...")
    regression_model, r_metrics = train_xgboost(X_train_r, y_train_r, X_holdout_r, y_holdout_r)
    logger.info("Regression AUC-ROC: %.4f", r_metrics["auc_roc"])

    # 5. LightGBM challenger (metrics only)
    logger.info("Training LightGBM challenger (25 trials each)...")
    lgb_b_metrics = train_lightgbm(X_train_b, y_train_b, X_holdout_b, y_holdout_b)
    lgb_r_metrics = train_lightgbm(X_train_r, y_train_r, X_holdout_r, y_holdout_r)

    if lgb_b_metrics["auc_roc"] - b_metrics["auc_roc"] > 0.02:
        logger.warning(
            "LightGBM breakout AUC (%.4f) exceeds XGBoost (%.4f) by >0.02 — "
            "consider switching production model",
            lgb_b_metrics["auc_roc"],
            b_metrics["auc_roc"],
        )
    if lgb_r_metrics["auc_roc"] - r_metrics["auc_roc"] > 0.02:
        logger.warning(
            "LightGBM regression AUC (%.4f) exceeds XGBoost (%.4f) by >0.02 — "
            "consider switching production model",
            lgb_r_metrics["auc_roc"],
            r_metrics["auc_roc"],
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
    # Current season has no N+1 label row — rebuild feature rows without label filter.
    # data_season "2025-26" → end-year integer 2026.
    # The most recent player data has season=2026; the feature window is (2026, 2025, 2024).
    current_season_int_val = int(data_season.split("-")[0]) + 1  # e.g. 2026 for "2025-26"
    current_feature_slice = {
        pid: [
            r
            for r in rows
            if r["season"]
            in (
                current_season_int_val,
                current_season_int_val - 1,
                current_season_int_val - 2,
            )
        ]
        for pid, rows in all_rows.items()
    }
    current_rows = [
        row
        for row in build_feature_matrix(current_feature_slice, season=current_season_int_val)
        if not row.get("stale_season") and row.get("position_type") != "goalie"
    ]
    # Wrap as dataset for _upsert_player_trends (labels unused for current season)
    current_dataset_wrapped: list[tuple[dict[str, Any], tuple[int, int]]] = [
        (row, (0, 0)) for row in current_rows
    ]

    # Use args.season (the training/target season, e.g. "2026-27"), NOT data_season.
    # GET /trends defaults to settings.current_season = "2026-27". Storing rows under
    # data_season ("2025-26") would cause the default query to return has_trends=False.
    _upsert_player_trends(
        db=db,
        season=args.season,
        dataset_current=current_dataset_wrapped,
        breakout_model=breakout_model,
        regression_model=regression_model,
    )

    logger.info("Phase 3d training pipeline complete. Season: %s", args.season)


if __name__ == "__main__":
    main()
