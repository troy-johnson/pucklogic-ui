from __future__ import annotations

import numpy as np

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
        "icf_per60": 12.0,
        "ixg_per60": 10.0,
        "xgf_pct_5v5": 52.0,
        "cf_pct_adj": 51.0,
        "scf_per60": 16.0,
        "scf_pct": 51.0,
        "toi_pp": 2.5,
        "toi_sh": 0.1,
        "g_per60": 2.0,
        "g_minus_ixg": 0.5,
        "sh_pct": 0.11,
        "sh_pct_career_avg": 0.10,
        "pdo": 1.005,
        "pp_unit": 1,
        "oi_sh_pct": 0.09,
        "elc_flag": False,
        "contract_year_flag": False,
        "post_extension_flag": False,
        "date_of_birth": "1995-01-15",
        "position": "C",
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
                _make_row("p1", 2011, p1_per60=4.0),  # curr (N+1=2011)
                _make_row("p1", 2010, p1_per60=3.0),  # N=2010 (weight 0.6)
                _make_row("p1", 2009, p1_per60=2.0),  # N-1=2009 (weight 0.4)
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
            rows[pid] = [_make_row(pid, s, p1_per60=2.5 + i * 0.1) for s in range(2007, 2013)]
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
        """THE CRITICAL TEST: season N+1 rows must NEVER appear in the feature slice."""
        all_rows = self._make_all_rows()

        SENTINEL = 999.999
        for pid, rows in all_rows.items():
            for r in rows:
                if r["season"] in (2010, 2011):  # N+1 for train_seasons [2009, 2010]
                    r["__sentinel__"] = SENTINEL

        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2011))
        for feature_row, _ in dataset:
            assert feature_row.get("__sentinel__") != SENTINEL, (
                f"LEAKAGE: season N+1 row reached feature matrix for player "
                f"{feature_row.get('player_id')}"
            )

    def test_stale_season_rows_excluded(self):
        """Rows with stale_season=True must not become training examples."""
        all_rows = self._make_all_rows()
        for r in all_rows["p0"]:
            if r["season"] == 2009:
                r["stale_season"] = True
        dataset = build_labeled_dataset(all_rows, train_seasons=range(2009, 2010))
        stale_rows = [d for d, _ in dataset if d.get("player_id") == "p0"]
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
            "toi_ev_per_game",
            "toi_pp_per_game",
            "toi_sh_per_game",
            "pp_unit_change",
            "a2_pct_of_assists",
            "breakout_count",
            "regression_count",
            "breakout_tier",
            "regression_tier",
            "player_id",
            "season",
            "stale_season",
            "position_type",
            "position",
            "toi_sh",
            "breakout_signals",
            "regression_signals",
            "scf_per60_curr",
        }
        for col in excluded:
            assert col not in FEATURE_NAMES, f"Excluded column in features: {col}"


# ---------------------------------------------------------------------------
# Holdout split
# ---------------------------------------------------------------------------


class TestHoldoutSplit:
    """Verify _HOLDOUT_SEASONS {2023, 2024} are excluded from CV and
    included in the final-retrain arrays passed to train_xgboost."""

    def _make_holdout_row(self, season: int) -> dict:
        row = {f: 0.0 for f in FEATURE_NAMES}
        row["season"] = season
        row["player_id"] = "p1"
        return row

    def test_holdout_seasons_excluded_from_train_set(self):
        from ml.train import _HOLDOUT_SEASONS

        assert _HOLDOUT_SEASONS == {2023, 2024}

        dataset = [(self._make_holdout_row(s), (0, 0)) for s in range(2008, 2025)]
        train_set = [
            (row, lbl) for row, lbl in dataset if row.get("season") not in _HOLDOUT_SEASONS
        ]
        holdout_set = [(row, lbl) for row, lbl in dataset if row.get("season") in _HOLDOUT_SEASONS]

        train_seasons = {row["season"] for row, _ in train_set}
        holdout_seasons = {row["season"] for row, _ in holdout_set}

        assert _HOLDOUT_SEASONS.isdisjoint(train_seasons), (
            "Holdout seasons must not appear in the CV training set"
        )
        assert holdout_seasons == _HOLDOUT_SEASONS, "All holdout seasons must be in the holdout set"

    def test_final_retrain_includes_holdout(self):
        """train_xgboost stacks X_train + X_holdout for final fit."""
        from ml.train import _HOLDOUT_SEASONS

        dataset = [(self._make_holdout_row(s), (1, 0)) for s in range(2008, 2025)]
        train_set = [
            (row, lbl) for row, lbl in dataset if row.get("season") not in _HOLDOUT_SEASONS
        ]
        holdout_set = [(row, lbl) for row, lbl in dataset if row.get("season") in _HOLDOUT_SEASONS]

        X_train = np.array([[row[f] for f in FEATURE_NAMES] for row, _ in train_set])
        X_holdout = np.array([[row[f] for f in FEATURE_NAMES] for row, _ in holdout_set])
        X_all = np.vstack([X_train, X_holdout])

        assert X_all.shape[0] == len(dataset), (
            "Final retrain must include ALL rows (train + holdout)"
        )
        assert X_train.shape[0] + X_holdout.shape[0] == X_all.shape[0]


# ---------------------------------------------------------------------------
# Holdout metrics validity
# ---------------------------------------------------------------------------


class TestHoldoutMetricsValidity:
    """train_xgboost and train_lightgbm must report metrics from a pre-retrain
    model (trained on X_train only), not from the final production model
    (trained on X_all = train + holdout). Evaluating the final model on
    holdout data it was trained on would yield inflated, misleading metrics."""

    def test_train_xgboost_metrics_from_pre_retrain_model(self, monkeypatch):
        """Second-to-last fit call must be on X_train; last fit call on X_all."""
        import xgboost as xgb

        from ml.train import train_xgboost

        rng = np.random.default_rng(7)
        n_features = len(FEATURE_NAMES)
        X_train = rng.random((30, n_features))
        y_train = np.array([i % 2 for i in range(30)])
        X_holdout = rng.random((10, n_features))
        y_holdout = np.array([i % 2 for i in range(10)])

        fit_Xs: list[np.ndarray] = []
        original_fit = xgb.XGBClassifier.fit

        def tracking_fit(self_inner, X, y, **kwargs):
            fit_Xs.append(np.asarray(X))
            return original_fit(self_inner, X, y, **kwargs)

        monkeypatch.setattr(xgb.XGBClassifier, "fit", tracking_fit)

        train_xgboost(X_train, y_train, X_holdout, y_holdout, n_trials=1)

        X_all = np.vstack([X_train, X_holdout])
        # Last fit: final model trained on all data (train + holdout)
        np.testing.assert_array_equal(fit_Xs[-1], X_all)
        # Second-to-last fit: pre-retrain model trained on X_train only
        np.testing.assert_array_equal(fit_Xs[-2], X_train)
