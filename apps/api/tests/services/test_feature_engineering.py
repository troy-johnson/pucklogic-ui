from __future__ import annotations

from typing import Any

import pytest

from services.feature_engineering import (
    _apply_weighted_rates,
    _compute_aliases,
    _compute_breakout_signals,
    _compute_projection_tier,
    _compute_regression_signals,
    build_feature_matrix,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RATE_STATS = [
    "icf_per60",
    "ixg_per60",
    "xgf_pct_5v5",
    "cf_pct_adj",
    "scf_per60",
    "scf_pct",
    "p1_per60",
    "toi_ev",
    "toi_pp",
    "toi_sh",
]


def _make_row(
    season: int = 2025,
    toi_ev: float = 21.3,
    icf_per60: float | None = 14.0,
    ixg_per60: float | None = 12.0,
    xgf_pct_5v5: float | None = 55.0,
    cf_pct_adj: float | None = 54.0,
    scf_per60: float | None = 18.0,
    scf_pct: float | None = 53.0,
    p1_per60: float | None = 3.5,
    toi_pp: float = 3.5,
    toi_sh: float = 0.2,
    # aliases / pass-through fields
    sh_pct: float | None = 0.115,
    sh_pct_career_avg: float | None = 0.110,
    g_minus_ixg: float | None = 0.5,
    g_per60: float | None = 2.8,
    oi_sh_pct: float | None = 0.095,
    pp_unit: int | None = 1,
    pdo: float = 1.010,
    elc_flag: bool = False,
    contract_year_flag: bool = False,
    post_extension_flag: bool = False,
    # players join fields
    date_of_birth: str = "1997-01-13",
    position: str = "C",  # NHL.com canonical: C/LW/RW/D/G — never "F"
) -> dict:
    return {
        "season": season,
        "toi_ev": toi_ev,
        "toi_pp": toi_pp,
        "toi_sh": toi_sh,
        "icf_per60": icf_per60,
        "ixg_per60": ixg_per60,
        "xgf_pct_5v5": xgf_pct_5v5,
        "cf_pct_adj": cf_pct_adj,
        "scf_per60": scf_per60,
        "scf_pct": scf_pct,
        "p1_per60": p1_per60,
        "sh_pct": sh_pct,
        "sh_pct_career_avg": sh_pct_career_avg,
        "g_minus_ixg": g_minus_ixg,
        "g_per60": g_per60,
        "oi_sh_pct": oi_sh_pct,
        "pp_unit": pp_unit,
        "pdo": pdo,
        "elc_flag": elc_flag,
        "contract_year_flag": contract_year_flag,
        "post_extension_flag": post_extension_flag,
        "date_of_birth": date_of_birth,
        "position": position,
    }


# ---------------------------------------------------------------------------
# Tests: _apply_weighted_rates
# ---------------------------------------------------------------------------


class TestApplyWeightedRates:
    def test_three_seasons_weighted_correctly(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=13.0),
            _make_row(season=2023, toi_ev=19.0, icf_per60=11.0),
        ]
        result = _apply_weighted_rates(rows)
        # icf_per60 = 15*0.5 + 13*0.3 + 11*0.2 = 7.5 + 3.9 + 2.2 = 13.6
        assert result["icf_per60"] == pytest.approx(13.6)

    def test_two_seasons_renormalizes_weights(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=13.0),
        ]
        result = _apply_weighted_rates(rows)
        # Weights [0.5, 0.3] → renormalized [0.625, 0.375]
        # icf_per60 = 15*0.625 + 13*0.375 = 9.375 + 4.875 = 14.25
        assert result["icf_per60"] == pytest.approx(14.25)

    def test_one_season_returns_that_seasons_value(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0, icf_per60=15.0)]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] == pytest.approx(15.0)

    def test_season_below_toi_threshold_excluded(self) -> None:
        # toi_ev = 4.9 < TOI_THRESHOLD (5.0) → excluded
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=4.9, icf_per60=5.0),  # excluded
        ]
        result = _apply_weighted_rates(rows)
        # Only 2025 qualifies; renormalized to weight [1.0]
        assert result["icf_per60"] == pytest.approx(15.0)

    def test_all_seasons_below_threshold_returns_none_stats(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=4.0, icf_per60=15.0),
        ]
        result = _apply_weighted_rates(rows)
        # Player excluded — all rate stats None
        assert result["icf_per60"] is None

    def test_null_stat_excluded_per_stat_only(self) -> None:
        # Season 2024 has null icf_per60 but valid xgf_pct_5v5
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0, xgf_pct_5v5=55.0),
            _make_row(season=2024, toi_ev=20.0, icf_per60=None, xgf_pct_5v5=53.0),
        ]
        result = _apply_weighted_rates(rows)
        # icf_per60: only 2025 contributes → weight [1.0] → 15.0
        assert result["icf_per60"] == pytest.approx(15.0)
        # xgf_pct_5v5: both seasons → [0.625, 0.375] → 55*0.625 + 53*0.375
        assert result["xgf_pct_5v5"] == pytest.approx(55.0 * 0.625 + 53.0 * 0.375)

    def test_all_rows_null_for_stat_returns_none(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=None),
            _make_row(season=2024, toi_ev=20.0, icf_per60=None),
        ]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] is None

    def test_all_rate_stats_in_result(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0)]
        result = _apply_weighted_rates(rows)
        for stat in _RATE_STATS:
            assert stat in result

    def test_zero_value_is_not_null(self) -> None:
        rows = [_make_row(season=2025, toi_ev=21.0, icf_per60=0.0)]
        result = _apply_weighted_rates(rows)
        assert result["icf_per60"] == pytest.approx(0.0)
        assert result["icf_per60"] is not None

    def test_qualifying_count_zero_when_all_below_threshold(self) -> None:
        rows = [_make_row(season=2025, toi_ev=4.0)]  # below threshold
        result = _apply_weighted_rates(rows)
        assert result["_qualifying_count"] == 0

    def test_qualifying_count_one_when_one_of_two_excluded(self) -> None:
        rows = [
            _make_row(season=2025, toi_ev=21.0, icf_per60=15.0),
            _make_row(season=2024, toi_ev=4.9, icf_per60=5.0),  # excluded
        ]
        result = _apply_weighted_rates(rows)
        assert result["_qualifying_count"] == 1


# ---------------------------------------------------------------------------
# Tests: _compute_aliases
# ---------------------------------------------------------------------------


class TestComputeAliases:
    def test_toi_aliases_renamed(self) -> None:
        weighted = {"toi_ev": 21.3, "toi_pp": 3.5, "toi_sh": 0.2, "icf_per60": 14.0}
        current = _make_row(season=2025)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["toi_ev_per_game"] == pytest.approx(21.3)
        assert result["toi_pp_per_game"] == pytest.approx(3.5)
        assert result["toi_sh_per_game"] == pytest.approx(0.2)

    def test_sh_pct_delta_computed_correctly(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=0.125, sh_pct_career_avg=0.110)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] == pytest.approx(0.125 - 0.110)

    def test_sh_pct_delta_none_when_sh_pct_missing(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=None, sh_pct_career_avg=0.110)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] is None

    def test_sh_pct_delta_none_when_career_avg_missing(self) -> None:
        weighted = {}
        current = _make_row(sh_pct=0.125, sh_pct_career_avg=None)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["sh_pct_delta"] is None

    def test_g_minus_ixg_passthrough(self) -> None:
        weighted = {}
        current = _make_row(g_minus_ixg=1.5)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["g_minus_ixg"] == pytest.approx(1.5)

    def test_g_per60_passthrough(self) -> None:
        weighted = {}
        current = _make_row(g_per60=2.8)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["g_per60"] == pytest.approx(2.8)

    def test_ixg_per60_curr_is_current_season(self) -> None:
        weighted = {"ixg_per60": 11.0}  # weighted avg — different from current
        current = _make_row(ixg_per60=13.5)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["ixg_per60_curr"] == pytest.approx(13.5)

    def test_age_computed_from_dob(self) -> None:
        # Season 2025 → Oct 1 2025; DoB 1997-01-13 → age 28
        weighted = {}
        current = _make_row(season=2025, date_of_birth="1997-01-13")
        result = _compute_aliases(weighted, current, prev=None)
        assert result["age"] == 28

    def test_age_birthday_after_oct1_rounds_down(self) -> None:
        # DoB 1997-11-01 — not yet 28 by Oct 1 2025
        weighted = {}
        current = _make_row(season=2025, date_of_birth="1997-11-01")
        result = _compute_aliases(weighted, current, prev=None)
        assert result["age"] == 27

    def test_icf_per60_delta_with_prev(self) -> None:
        weighted = {}
        current = _make_row(icf_per60=15.0)
        prev = _make_row(icf_per60=12.0)
        result = _compute_aliases(weighted, current, prev)
        assert result["icf_per60_delta"] == pytest.approx(3.0)

    def test_icf_per60_delta_none_without_prev(self) -> None:
        weighted = {}
        current = _make_row(icf_per60=15.0)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["icf_per60_delta"] is None

    def test_pp_unit_change_pp2_to_pp1(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        prev = _make_row(pp_unit=2)
        result = _compute_aliases(weighted, current, prev)
        assert result["pp_unit_change"] == "PP2→PP1"

    def test_pp_unit_change_none_when_no_change(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        prev = _make_row(pp_unit=1)
        result = _compute_aliases(weighted, current, prev)
        assert result["pp_unit_change"] is None

    def test_pp_unit_change_none_without_prev(self) -> None:
        weighted = {}
        current = _make_row(pp_unit=1)
        result = _compute_aliases(weighted, current, prev=None)
        assert result["pp_unit_change"] is None

    def test_a2_pct_of_assists_always_none(self) -> None:
        weighted = {}
        current = _make_row()
        result = _compute_aliases(weighted, current, prev=None)
        assert result["a2_pct_of_assists"] is None


# ---------------------------------------------------------------------------
# Tests: _compute_breakout_signals
# ---------------------------------------------------------------------------


class TestComputeBreakoutSignals:
    """Each signal: fires on threshold-meeting value; suppresses below threshold and on None."""

    def _features(self, **overrides: Any) -> dict:
        base = {
            "g_per60": 2.0,
            "ixg_per60_curr": 2.5,  # g_per60 < ixg * 0.85 → 2.0 < 2.125 → True
            "sh_pct_delta": -0.04,  # below_career → True
            "icf_per60_delta": 0.6,  # rising_shot_gen → True
            "pp_unit_change": "PP2→PP1",  # pp_promotion → True
            "age": 22,  # prime_age_window → True
            "xgf_pct_5v5": 53.0,  # strong_underlying → True
            "pdo": 0.970,  # bad_luck_pdo → True
            "elc_flag": True,
            "toi_ev_per_game": 15.0,  # elc_deployed → True
        }
        base.update(overrides)
        return base

    def test_g_below_ixg_fires(self) -> None:
        f = self._features(g_per60=2.0, ixg_per60_curr=2.5)  # 2.0 < 2.5*0.85=2.125
        assert _compute_breakout_signals(f)["g_below_ixg"] is True

    def test_g_below_ixg_suppressed(self) -> None:
        f = self._features(g_per60=2.5, ixg_per60_curr=2.5)  # 2.5 >= 2.125
        assert _compute_breakout_signals(f)["g_below_ixg"] is False

    def test_g_below_ixg_none_input(self) -> None:
        f = self._features(g_per60=None, ixg_per60_curr=2.5)
        assert _compute_breakout_signals(f)["g_below_ixg"] is False

    def test_sh_pct_below_career_fires(self) -> None:
        f = self._features(sh_pct_delta=-0.031)  # < -0.03
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is True

    def test_sh_pct_below_career_suppressed(self) -> None:
        f = self._features(sh_pct_delta=-0.03)  # not < -0.03 (boundary)
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is False

    def test_sh_pct_below_career_none(self) -> None:
        f = self._features(sh_pct_delta=None)
        assert _compute_breakout_signals(f)["sh_pct_below_career"] is False

    def test_rising_shot_gen_fires(self) -> None:
        f = self._features(icf_per60_delta=0.51)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is True

    def test_rising_shot_gen_suppressed(self) -> None:
        f = self._features(icf_per60_delta=0.5)  # not > 0.5 (boundary)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is False

    def test_rising_shot_gen_none(self) -> None:
        f = self._features(icf_per60_delta=None)
        assert _compute_breakout_signals(f)["rising_shot_gen"] is False

    def test_pp_promotion_fires(self) -> None:
        f = self._features(pp_unit_change="PP2→PP1")
        assert _compute_breakout_signals(f)["pp_promotion"] is True

    def test_pp_promotion_suppressed(self) -> None:
        f = self._features(pp_unit_change=None)
        assert _compute_breakout_signals(f)["pp_promotion"] is False

    def test_prime_age_window_fires_at_20(self) -> None:
        assert _compute_breakout_signals(self._features(age=20))["prime_age_window"] is True

    def test_prime_age_window_fires_at_25(self) -> None:
        assert _compute_breakout_signals(self._features(age=25))["prime_age_window"] is True

    def test_prime_age_window_suppressed_at_26(self) -> None:
        assert _compute_breakout_signals(self._features(age=26))["prime_age_window"] is False

    def test_prime_age_window_suppressed_at_19(self) -> None:
        # Lower bound: must be >= 20
        assert _compute_breakout_signals(self._features(age=19))["prime_age_window"] is False

    def test_prime_age_window_none(self) -> None:
        assert _compute_breakout_signals(self._features(age=None))["prime_age_window"] is False

    def test_strong_underlying_fires(self) -> None:
        f = self._features(xgf_pct_5v5=52.1)
        assert _compute_breakout_signals(f)["strong_underlying"] is True

    def test_strong_underlying_suppressed(self) -> None:
        f = self._features(xgf_pct_5v5=52.0)
        assert _compute_breakout_signals(f)["strong_underlying"] is False

    def test_strong_underlying_none(self) -> None:
        f = self._features(xgf_pct_5v5=None)
        assert _compute_breakout_signals(f)["strong_underlying"] is False

    def test_bad_luck_pdo_fires(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=0.974))["bad_luck_pdo"] is True

    def test_bad_luck_pdo_suppressed(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=0.975))["bad_luck_pdo"] is False

    def test_bad_luck_pdo_none(self) -> None:
        assert _compute_breakout_signals(self._features(pdo=None))["bad_luck_pdo"] is False

    def test_elc_deployed_fires(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=14.0)
        assert _compute_breakout_signals(f)["elc_deployed"] is True

    def test_elc_deployed_suppressed_low_toi(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=13.9)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_elc_deployed_suppressed_not_elc(self) -> None:
        f = self._features(elc_flag=False, toi_ev_per_game=15.0)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_elc_deployed_none_toi(self) -> None:
        f = self._features(elc_flag=True, toi_ev_per_game=None)
        assert _compute_breakout_signals(f)["elc_deployed"] is False

    def test_all_eight_signals_present_in_result(self) -> None:
        result = _compute_breakout_signals(self._features())
        expected_keys = {
            "g_below_ixg",
            "sh_pct_below_career",
            "rising_shot_gen",
            "pp_promotion",
            "prime_age_window",
            "strong_underlying",
            "bad_luck_pdo",
            "elc_deployed",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Tests: _compute_regression_signals
# ---------------------------------------------------------------------------


class TestComputeRegressionSignals:
    def _features(self, **overrides: Any) -> dict:
        base = {
            "g_per60": 3.5,
            "ixg_per60_curr": 2.5,  # g > ixg * 1.20 → 3.5 > 3.0 → True
            "sh_pct_delta": 0.05,  # sh_pct_above_career → True
            "pdo": 1.030,  # high_pdo → True
            "oi_sh_pct": 0.12,  # high_oi_sh_pct → True
            "a2_pct_of_assists": None,  # always None (D8)
            "age": 31,
            "position": "C",  # age_declining → True (NHL.com canonical: C/LW/RW, NOT "F")
            "icf_per60_delta": -0.6,  # declining_shot_gen → True
        }
        base.update(overrides)
        return base

    def test_g_above_ixg_fires(self) -> None:
        f = self._features(g_per60=3.5, ixg_per60_curr=2.5)  # 3.5 > 2.5*1.20=3.0
        assert _compute_regression_signals(f)["g_above_ixg"] is True

    def test_g_above_ixg_suppressed(self) -> None:
        f = self._features(g_per60=3.0, ixg_per60_curr=2.5)  # 3.0 == 3.0, not >
        assert _compute_regression_signals(f)["g_above_ixg"] is False

    def test_g_above_ixg_none_input(self) -> None:
        f = self._features(g_per60=None)
        assert _compute_regression_signals(f)["g_above_ixg"] is False

    def test_sh_pct_above_career_fires(self) -> None:
        f = self._features(sh_pct_delta=0.041)
        assert _compute_regression_signals(f)["sh_pct_above_career"] is True

    def test_sh_pct_above_career_suppressed(self) -> None:
        f = self._features(sh_pct_delta=0.04)  # not > 0.04
        assert _compute_regression_signals(f)["sh_pct_above_career"] is False

    def test_sh_pct_above_career_none(self) -> None:
        f = self._features(sh_pct_delta=None)
        assert _compute_regression_signals(f)["sh_pct_above_career"] is False

    def test_high_pdo_fires(self) -> None:
        f = self._features(pdo=1.026)
        assert _compute_regression_signals(f)["high_pdo"] is True

    def test_high_pdo_suppressed(self) -> None:
        f = self._features(pdo=1.025)  # not > 1.025
        assert _compute_regression_signals(f)["high_pdo"] is False

    def test_high_pdo_none(self) -> None:
        f = self._features(pdo=None)
        assert _compute_regression_signals(f)["high_pdo"] is False

    def test_high_oi_sh_pct_fires(self) -> None:
        f = self._features(oi_sh_pct=0.111)
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is True

    def test_high_oi_sh_pct_suppressed(self) -> None:
        f = self._features(oi_sh_pct=0.11)  # not > 0.11
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is False

    def test_high_oi_sh_pct_none(self) -> None:
        f = self._features(oi_sh_pct=None)
        assert _compute_regression_signals(f)["high_oi_sh_pct"] is False

    def test_high_secondary_pct_always_false(self) -> None:
        # D8: a1 counting stat not in schema; signal disabled in Phase 3c
        f = self._features(a2_pct_of_assists=None)
        assert _compute_regression_signals(f)["high_secondary_pct"] is False

    def test_age_declining_fires_forward_over_30(self) -> None:
        # DB stores NHL.com canonical positions: C, LW, RW for forwards — NOT "F"
        f = self._features(age=31, position="C")
        assert _compute_regression_signals(f)["age_declining"] is True

    def test_age_declining_fires_lw_and_rw(self) -> None:
        lw = _compute_regression_signals(self._features(age=31, position="LW"))
        rw = _compute_regression_signals(self._features(age=31, position="RW"))
        assert lw["age_declining"] is True
        assert rw["age_declining"] is True

    def test_age_declining_suppressed_at_30(self) -> None:
        f = self._features(age=30, position="C")  # not > 30
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_suppressed_for_defenseman(self) -> None:
        f = self._features(age=31, position="D")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_suppressed_for_goalie(self) -> None:
        f = self._features(age=31, position="G")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_age_declining_none_age(self) -> None:
        f = self._features(age=None, position="C")
        assert _compute_regression_signals(f)["age_declining"] is False

    def test_declining_shot_gen_fires(self) -> None:
        f = self._features(icf_per60_delta=-0.51)
        assert _compute_regression_signals(f)["declining_shot_gen"] is True

    def test_declining_shot_gen_suppressed(self) -> None:
        f = self._features(icf_per60_delta=-0.5)  # not < -0.5
        assert _compute_regression_signals(f)["declining_shot_gen"] is False

    def test_declining_shot_gen_none(self) -> None:
        f = self._features(icf_per60_delta=None)
        assert _compute_regression_signals(f)["declining_shot_gen"] is False

    def test_all_seven_signals_present(self) -> None:
        result = _compute_regression_signals(self._features())
        expected_keys = {
            "g_above_ixg",
            "sh_pct_above_career",
            "high_pdo",
            "high_oi_sh_pct",
            "high_secondary_pct",
            "age_declining",
            "declining_shot_gen",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Tests: _compute_projection_tier
# ---------------------------------------------------------------------------


class TestComputeProjectionTier:
    def test_four_signals_high(self) -> None:
        assert _compute_projection_tier(4) == "HIGH"

    def test_five_signals_high(self) -> None:
        assert _compute_projection_tier(5) == "HIGH"

    def test_eight_signals_high(self) -> None:
        assert _compute_projection_tier(8) == "HIGH"

    def test_three_signals_medium(self) -> None:
        assert _compute_projection_tier(3) == "MEDIUM"

    def test_two_signals_low(self) -> None:
        assert _compute_projection_tier(2) == "LOW"

    def test_one_signal_none(self) -> None:
        assert _compute_projection_tier(1) is None

    def test_zero_signals_none(self) -> None:
        assert _compute_projection_tier(0) is None


# ---------------------------------------------------------------------------
# Tests: build_feature_matrix
# ---------------------------------------------------------------------------


class TestBuildFeatureMatrix:
    """Round-trip and integration tests for build_feature_matrix."""

    def _grouped(self, player_id: str = "p-mcdavid", seasons: int = 3) -> dict:
        rows = []
        for i in range(seasons):
            season = 2025 - i
            row = _make_row(
                season=season,
                toi_ev=21.0 - i,
                icf_per60=14.0 - i * 0.5,
                ixg_per60=12.0,
            )
            row["player_id"] = player_id
            rows.append(row)
        return {player_id: rows}

    def test_returns_list(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert isinstance(result, list)

    def test_one_dict_per_player(self) -> None:
        grouped = {
            "p-mcdavid": self._grouped()["p-mcdavid"],
            "p-draisaitl": self._grouped("p-draisaitl")["p-draisaitl"],
        }
        result = build_feature_matrix(grouped, season=2025)
        assert len(result) == 2

    def test_player_id_in_output(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert result[0]["player_id"] == "p-mcdavid"

    def test_weighted_rate_stats_in_output(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        for stat in _RATE_STATS:
            assert stat in result[0], f"Missing stat: {stat}"

    def test_breakout_tier_present(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert "breakout_tier" in result[0]

    def test_regression_tier_present(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert "regression_tier" in result[0]

    def test_breakout_signals_dict_in_output(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert isinstance(result[0]["breakout_signals"], dict)
        assert len(result[0]["breakout_signals"]) == 8

    def test_regression_signals_dict_in_output(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert isinstance(result[0]["regression_signals"], dict)
        assert len(result[0]["regression_signals"]) == 7

    def test_player_with_zero_qualifying_seasons_excluded(self) -> None:
        # toi_ev below threshold → excluded from output
        row = _make_row(season=2025, toi_ev=2.0)
        row["player_id"] = "p-healthy-scratch"
        result = build_feature_matrix({"p-healthy-scratch": [row]}, season=2025)
        assert result == []

    def test_both_tiers_independently_tracked(self) -> None:
        """breakout_tier and regression_tier are independent — both HIGH simultaneously is valid.

        Use two separate players: one with 4 breakout signals, one with 4 regression signals.
        """
        # 4 breakout signals: g_below_ixg + sh_pct_below_career + prime_age_window + bad_luck_pdo
        breakout_row = _make_row(
            season=2025,
            toi_ev=21.0,
            g_per60=1.5,
            ixg_per60=3.0,  # g(1.5) < ixg(3.0)*0.85=2.55 → g_below_ixg True
            sh_pct=0.06,
            sh_pct_career_avg=0.11,  # delta=-0.05 < -0.03 → sh_pct_below_career True
            pdo=0.960,  # bad_luck_pdo True
            date_of_birth="2003-01-01",  # age=22 → prime_age_window True
        )
        breakout_row["player_id"] = "p-breakout"

        # 4 regression signals: g_above_ixg + sh_pct_above_career + high_pdo + high_oi_sh_pct
        regression_row = _make_row(
            season=2025,
            toi_ev=21.0,
            g_per60=4.0,
            ixg_per60=3.0,  # g(4.0) > ixg(3.0)*1.20=3.6 → g_above_ixg True
            sh_pct=0.16,
            sh_pct_career_avg=0.11,  # delta=+0.05 > 0.04 → sh_pct_above_career True
            pdo=1.030,  # high_pdo True
            oi_sh_pct=0.12,  # high_oi_sh_pct True
            date_of_birth="1985-01-01",  # age=40 → age_declining suppressed (only C/LW/RW)
        )
        regression_row["player_id"] = "p-regression"

        grouped = {
            "p-breakout": [breakout_row],
            "p-regression": [regression_row],
        }
        result = {r["player_id"]: r for r in build_feature_matrix(grouped, season=2025)}
        assert result["p-breakout"]["breakout_tier"] == "HIGH"
        assert result["p-regression"]["regression_tier"] == "HIGH"

    def test_stale_season_player_falls_back_to_most_recent(self) -> None:
        """Player missing current-season row falls back to most recent available row."""
        # Only has a 2024 row; requested season=2025
        row = _make_row(season=2024, toi_ev=21.0)
        row["player_id"] = "p-injured"
        result = build_feature_matrix({"p-injured": [row]}, season=2025)
        assert len(result) == 1
        assert result[0]["season"] == 2024
        assert result[0]["stale_season"] is True

    def test_stale_season_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        row = _make_row(season=2024, toi_ev=21.0)
        row["player_id"] = "p-injured"
        with caplog.at_level(logging.WARNING, logger="services.feature_engineering"):
            build_feature_matrix({"p-injured": [row]}, season=2025)
        assert any("stale" in msg.lower() or "missing" in msg.lower() for msg in caplog.messages)

    def test_stale_season_false_for_current_player(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert result[0]["stale_season"] is False

    def test_stale_season_true_when_no_current_row(self) -> None:
        row = _make_row(season=2024, toi_ev=21.0)
        row["player_id"] = "p-injured"
        result = build_feature_matrix({"p-injured": [row]}, season=2025)
        assert result[0]["stale_season"] is True

    def test_position_type_skater_for_forward(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        assert result[0]["position_type"] == "skater"

    def test_position_type_skater_for_defenseman(self) -> None:
        row = _make_row(season=2025, toi_ev=21.0, position="D")
        row["player_id"] = "p-d"
        result = build_feature_matrix({"p-d": [row]}, season=2025)
        assert result[0]["position_type"] == "skater"

    def test_position_type_goalie(self) -> None:
        row = _make_row(season=2025, toi_ev=21.0, position="G")
        row["player_id"] = "p-goalie"
        result = build_feature_matrix({"p-goalie": [row]}, season=2025)
        assert result[0]["position_type"] == "goalie"

    def test_all_required_keys_in_output(self) -> None:
        result = build_feature_matrix(self._grouped(), season=2025)
        player = result[0]
        required_keys = {
            "player_id",
            "season",
            "stale_season",
            "position_type",
            # weighted rates
            "icf_per60",
            "ixg_per60",
            "xgf_pct_5v5",
            "cf_pct_adj",
            "scf_per60",
            "scf_pct",
            "p1_per60",
            "hits_per60",
            "blocks_per60",
            "toi_ev_per_game",
            "toi_pp_per_game",
            "toi_sh_per_game",
            # current-season pass-throughs
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
            "position",
            # deltas
            "icf_per60_delta",
            "pp_unit_change",
            "a2_pct_of_assists",
            # signals
            "breakout_signals",
            "regression_signals",
            "breakout_count",
            "regression_count",
            "breakout_tier",
            "regression_tier",
        }
        missing = required_keys - set(player.keys())
        assert not missing, f"Missing keys: {missing}"


# ---------------------------------------------------------------------------
# Tests: physical stat Marcel weight overrides
# ---------------------------------------------------------------------------


class TestPhysicalStatWeights:
    def test_hits_per60_uses_physical_weights(self) -> None:
        """hits_per60 should use [0.6, 0.25, 0.15], not [0.5, 0.3, 0.2]."""
        # Three seasons newest-first, each with toi_ev above threshold
        rows = [
            {**_make_row(season=2025), "hits_per60": 4.0},  # current (weight 0.6)
            {**_make_row(season=2024), "hits_per60": 2.0},  # yr -1  (weight 0.25)
            {**_make_row(season=2023), "hits_per60": 1.0},  # yr -2  (weight 0.15)
        ]
        result = _apply_weighted_rates(rows)
        # Normalized: 0.6/1.0=0.6, 0.25/1.0=0.25, 0.15/1.0=0.15
        expected = 0.6 * 4.0 + 0.25 * 2.0 + 0.15 * 1.0
        assert result["hits_per60"] == pytest.approx(expected)

    def test_standard_stats_unaffected_by_override(self) -> None:
        """icf_per60 should still use [0.5, 0.3, 0.2] weights, not [0.6, 0.25, 0.15]."""
        rows = [
            {**_make_row(season=2025), "icf_per60": 20.0},  # current  (weight 0.5)
            {**_make_row(season=2024), "icf_per60": 15.0},  # yr -1    (weight 0.3)
            {**_make_row(season=2023), "icf_per60": 10.0},  # yr -2    (weight 0.2)
        ]
        result = _apply_weighted_rates(rows)
        # With [0.5, 0.3, 0.2]: 0.5*20 + 0.3*15 + 0.2*10 = 17.5
        # With [0.6, 0.25, 0.15]: 0.6*20 + 0.25*15 + 0.15*10 = 17.75  ← different
        expected = 0.5 * 20.0 + 0.3 * 15.0 + 0.2 * 10.0
        assert result["icf_per60"] == pytest.approx(expected)
        assert result["icf_per60"] != pytest.approx(0.6 * 20.0 + 0.25 * 15.0 + 0.15 * 10.0)
