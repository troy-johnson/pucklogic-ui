from __future__ import annotations

import pytest

from services.projections import (
    aggregate_projections,
    apply_scoring_config,
    compute_vorp,
    compute_weighted_stats,
)


def _make_row(source_name: str, weight: float, **stats: int | None) -> dict:
    return {"source_name": source_name, "source_weight": weight, **stats}


class TestComputeWeightedStats:
    def test_single_source_returns_stat(self) -> None:
        rows = [_make_row("dobber", 10, g=30, a=45, sog=None)]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(30.0)
        assert result["a"] == pytest.approx(45.0)

    def test_null_stat_is_null_when_no_source_projects_it(self) -> None:
        rows = [_make_row("dobber", 10, g=30, a=None)]
        result = compute_weighted_stats(rows)
        assert result["a"] is None

    def test_null_excluded_per_stat(self) -> None:
        """If source A projects g=30 and source B does not (null), only A's g counts."""
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 10, g=None),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(30.0)

    def test_weighted_average_across_sources(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 10, g=40),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(35.0)

    def test_unequal_weights(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30),
            _make_row("hashtag", 30, g=60),
        ]
        # g = (30*10 + 60*30) / (10 + 30) = (300 + 1800) / 40 = 52.5
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(52.5)

    def test_zero_stat_is_distinct_from_null(self) -> None:
        rows = [_make_row("dobber", 10, g=0)]
        result = compute_weighted_stats(rows)
        assert result["g"] == pytest.approx(0.0)
        assert result["g"] is not None

    def test_all_nulls_returns_null(self) -> None:
        rows = [
            _make_row("dobber", 10, g=None),
            _make_row("hashtag", 10, g=None),
        ]
        result = compute_weighted_stats(rows)
        assert result["g"] is None

    def test_returns_all_stat_keys(self) -> None:
        rows = [_make_row("dobber", 10, g=30)]
        result = compute_weighted_stats(rows)
        for stat in ["g", "a", "ppp", "sog", "hits", "blocks", "gp"]:
            assert stat in result

    def test_source_count_counts_sources_with_any_non_null_stat(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30),   # projects g
            _make_row("hashtag", 10, g=None), # projects nothing → not counted
        ]
        result = compute_weighted_stats(rows)
        assert result["_source_count"] == 1

    def test_source_count_two_sources_projecting_different_stats(self) -> None:
        rows = [
            _make_row("dobber", 10, g=30, hits=None),
            _make_row("hashtag", 10, g=None, hits=100),
        ]
        result = compute_weighted_stats(rows)
        assert result["_source_count"] == 2
        assert result["g"] == pytest.approx(30.0)   # only dobber
        assert result["hits"] == pytest.approx(100.0)  # only hashtag


class TestApplyScoringConfig:
    def test_basic_scoring(self) -> None:
        stats = {"g": 30.0, "a": 45.0, "ppp": 20.0, "sog": None}
        config = {"g": 3.0, "a": 2.0, "ppp": 1.0, "sog": 0.5}
        # g=30*3=90, a=45*2=90, ppp=20*1=20, sog=null→0
        assert apply_scoring_config(stats, config) == pytest.approx(200.0)

    def test_null_stat_contributes_zero(self) -> None:
        stats = {"g": None}
        config = {"g": 3.0}
        assert apply_scoring_config(stats, config) == pytest.approx(0.0)

    def test_unrecognised_config_key_ignored(self) -> None:
        stats = {"g": 10.0}
        config = {"g": 3.0, "fake_stat": 99.0}
        assert apply_scoring_config(stats, config) == pytest.approx(30.0)

    def test_empty_stats_returns_zero(self) -> None:
        assert apply_scoring_config({}, {"g": 3.0}) == pytest.approx(0.0)

    def test_zero_weight_stat_not_counted(self) -> None:
        stats = {"g": 30.0, "hits": 100.0}
        config = {"g": 3.0, "hits": 0.0}
        assert apply_scoring_config(stats, config) == pytest.approx(90.0)


class TestComputeVorp:
    def _make_players(self, fps: list[float | None]) -> list[dict]:
        return [
            {
                "player_id": f"p{i}",
                "default_position": "C",
                "projected_fantasy_points": fp,
            }
            for i, fp in enumerate(fps)
        ]

    def _make_profile(
        self, num_teams: int = 10, c_slots: int = 2
    ) -> dict:
        return {
            "num_teams": num_teams,
            "roster_slots": {"C": c_slots, "LW": 2, "RW": 2, "D": 4, "G": 2},
        }

    def test_replacement_level_is_nth_player(self) -> None:
        # 10 teams * 2 C slots = 20 starters; replacement = rank 21
        fps = list(range(100, 79, -1))  # 21 players: 100, 99, ..., 80
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at index 20 (0-based) = 80 FP
        # player 0 (100 FP) → vorp = 100 - 80 = 20
        assert result["p0"] == pytest.approx(20.0)

    def test_replacement_level_player_has_zero_vorp(self) -> None:
        fps = list(range(100, 79, -1))  # 21 players: 100, 99, ..., 80
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at index 20 (rank 21) = 80 FP → vorp = 0
        assert result["p20"] == pytest.approx(0.0)

    def test_player_below_replacement_has_negative_vorp(self) -> None:
        # 22 players; replacement threshold = 10 teams × 2 slots + 1 = 21
        fps = list(range(100, 78, -1))  # 22 players: 100, 99, ..., 79
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement level = player at rank 21 (index 20) = 80 FP
        # player at index 21 has 79 FP → vorp = 79 − 80 = −1
        assert result["p21"] == pytest.approx(-1.0)

    def test_null_fp_returns_null_vorp(self) -> None:
        fps = [100.0, None]
        players = self._make_players(fps)
        result = compute_vorp(players, self._make_profile(1, 1))
        assert result["p1"] is None

    def test_fewer_players_than_replacement_uses_last(self) -> None:
        # Only 3 C players but replacement threshold is 21 → use last (lowest FP)
        players = self._make_players([100.0, 90.0, 80.0])
        result = compute_vorp(players, self._make_profile(10, 2))
        # replacement = 80 (last available)
        assert result["p0"] == pytest.approx(20.0)
        assert result["p2"] == pytest.approx(0.0)

    def test_vorp_null_when_no_players_in_position(self) -> None:
        players = [{"player_id": "p1", "default_position": "G", "projected_fantasy_points": 50.0}]
        profile = {"num_teams": 10, "roster_slots": {"C": 2}}  # no G slot
        result = compute_vorp(players, profile)
        assert result["p1"] is None

    def test_util_and_bn_excluded_from_replacement_level(self) -> None:
        """UTIL and BN roster slots must not inflate replacement-level thresholds."""
        players = self._make_players([100.0, 90.0, 80.0])
        profile = {
            "num_teams": 1,
            "roster_slots": {"C": 1, "UTIL": 2, "BN": 4},
        }
        result = compute_vorp(players, profile)
        # replacement level uses C=1 slot only: threshold = 1*1 = index 1 = 90
        assert result["p0"] == pytest.approx(10.0)


class TestAggregateProjections:
    """Integration test — exercises the full pipeline with minimal mocked data."""

    def _make_db_rows(self) -> list[dict]:
        base = {
            "season": "2025-26",
            "a": None, "plus_minus": None, "pim": None,
            "ppg": None, "ppa": None, "ppp": None,
            "shg": None, "sha": None, "shp": None,
            "sog": None, "fow": None, "fol": None,
            "hits": None, "blocks": None, "gp": 82,
            "gs": None, "w": None, "l": None, "ga": None,
            "sa": None, "sv": None, "sv_pct": None, "so": None, "otl": None,
        }
        return [
            {
                **base,
                "player_id": "p1",
                "g": 50,
                "sources": {"name": "dobber", "is_paid": False, "user_id": None},
                "players": {"name": "McDavid", "team": "EDM", "position": "C"},
                "player_platform_positions": [{"positions": ["C"]}],
                "schedule_scores": [{"season": "2025-26", "schedule_score": 0.8, "off_night_games": 24}],  # noqa: E501
            },
            {
                **base,
                "player_id": "p2",
                "g": 30,
                "sources": {"name": "dobber", "is_paid": False, "user_id": None},
                "players": {"name": "Smith", "team": "DAL", "position": "LW"},
                "player_platform_positions": [{"positions": ["LW"]}],
                "schedule_scores": [],
            },
        ]

    def test_returns_ranked_players(self) -> None:
        rows = self._make_db_rows()
        source_weights = {"dobber": 10}
        scoring_config = {"g": 3.0}
        result = aggregate_projections(rows, source_weights, scoring_config)
        assert len(result) == 2

    def test_sorted_by_fantasy_points_descending(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        fps = [r["projected_fantasy_points"] for r in result if r["projected_fantasy_points"] is not None]  # noqa: E501
        assert fps == sorted(fps, reverse=True)

    def test_composite_rank_assigned(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        assert result[0]["composite_rank"] == 1
        assert result[1]["composite_rank"] == 2

    def test_schedule_score_attached(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        p1 = next(r for r in result if r["player_id"] == "p1")
        assert p1["schedule_score"] == pytest.approx(0.8)
        assert p1["off_night_games"] == 24

    def test_missing_schedule_score_is_null(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        p2 = next(r for r in result if r["player_id"] == "p2")
        assert p2["schedule_score"] is None
        assert p2["off_night_games"] is None

    def test_vorp_computed_when_profile_provided(self) -> None:
        rows = self._make_db_rows()
        profile = {"num_teams": 1, "roster_slots": {"C": 1, "LW": 1}}
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0}, profile)
        for r in result:
            assert "vorp" in r

    def test_vorp_null_when_no_profile(self) -> None:
        rows = self._make_db_rows()
        result = aggregate_projections(rows, {"dobber": 10}, {"g": 3.0})
        for r in result:
            assert r["vorp"] is None

    def test_unknown_source_weight_produces_null_fp(self) -> None:
        rows = self._make_db_rows()
        # "ghost_source" not in DB rows — no matching source → null FP
        result = aggregate_projections(rows, {"ghost_source": 10}, {"g": 3.0})
        for r in result:
            assert r["projected_fantasy_points"] is None

    def test_zero_weight_source_produces_null_fp(self) -> None:
        rows = self._make_db_rows()
        source_name = rows[0]["sources"]["name"]  # "dobber"
        result = aggregate_projections(rows, {source_name: 0}, {"g": 3.0})
        for r in result:
            assert r["projected_fantasy_points"] is None
