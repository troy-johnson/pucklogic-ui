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
# Applied independently here — not delegated to build_feature_matrix.
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
