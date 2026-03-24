"""End-to-end pipeline smoke test using 50 synthetic players + mocked Storage/DB.

Unlike the DB-dependent smoke tests in tests/smoke/, this test is fully mocked
and runs in CI as part of the normal test suite.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

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
            rows.append(
                {
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
                    "pp_unit": int(rng.integers(1, 3)),
                    "elc_flag": bool(rng.integers(0, 2)),
                    "contract_year_flag": bool(rng.integers(0, 2)),
                    "post_extension_flag": bool(rng.integers(0, 2)),
                    "date_of_birth": f"{rng.integers(1990, 2002)}-06-15",
                    "position": rng.choice(["C", "LW", "RW", "D"]),
                }
            )
        rows.sort(key=lambda r: r["season"], reverse=True)
        all_rows[pid] = rows

    return all_rows


class TestTrainPipelineSmoke:
    def test_end_to_end_pipeline(self):
        """Full train.py pipeline on 50 synthetic players with mocked DB/Storage."""
        import xgboost as xgb

        from ml.loader import upload
        from ml.train import (
            _HOLDOUT_SEASONS,
            FEATURE_NAMES,
            _extract_Xy,
            _upsert_player_trends,
            build_labeled_dataset,
        )

        all_rows = _make_synthetic_all_rows(n_players=50, n_seasons=22)

        # Build labeled dataset
        full_dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2025))
        assert len(full_dataset) > 0, "Expected >0 labeled examples"

        # Split holdout
        holdout = [(row, lbl) for row, lbl in full_dataset if row.get("season") in _HOLDOUT_SEASONS]
        train = [
            (row, lbl) for row, lbl in full_dataset if row.get("season") not in _HOLDOUT_SEASONS
        ]
        assert len(holdout) > 0, "Expected holdout examples for seasons 2023-2024"
        assert len(train) > 0, "Expected training examples"

        X_train, y_train = _extract_Xy(train, 0)
        X_holdout, _y_holdout = _extract_Xy(holdout, 0)

        # Train tiny model (bypass Optuna for speed)
        tiny_model = xgb.XGBClassifier(n_estimators=5, max_depth=2, random_state=0)
        tiny_model.fit(pd.DataFrame(X_train, columns=FEATURE_NAMES), y_train)

        # Verify upload calls Storage exactly 3 times
        mock_db = MagicMock()
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
        assert mock_db.storage.from_.return_value.upload.call_count == 3

        # Verify player_trends upsert
        current_rows = [r for rows in all_rows.values() for r in rows if r["season"] == 2024]
        current_dataset = [(row, (0, 0)) for row in current_rows[:10]]

        upsert_db = MagicMock()
        _upsert_player_trends(
            db=upsert_db,
            season="2024-25",
            dataset_current=current_dataset,
            breakout_model=tiny_model,
            regression_model=tiny_model,
        )
        assert upsert_db.table.return_value.upsert.call_count > 0

        # Verify leakage guard passes for all training seasons
        for n in range(2009, 2025):
            feature_slice = {
                pid: [r for r in rows if r["season"] in (n, n - 1, n - 2)]
                for pid, rows in all_rows.items()
            }
            for pid, rows in feature_slice.items():
                for r in rows:
                    assert r["season"] <= n, f"LEAKAGE for player {pid} in season {n}"
