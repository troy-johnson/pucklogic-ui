"""
Unit tests for services/rankings.py.

TDD: tests define the expected behaviour of compute_weighted_rankings and
flatten_db_rankings — no DB, no network, no filesystem.
"""

from __future__ import annotations

import pytest

from services.rankings import (
    build_close_snapshot_from_recipe,
    compute_weighted_rankings,
    flatten_db_rankings,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TWO_SOURCE_ROWS = [
    {
        "rank": 1,
        "season": "2025-26",
        "players": {
            "id": "p1",
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
        },
        "sources": {"name": "nhl_com", "display_name": "NHL.com"},
    },
    {
        "rank": 2,
        "season": "2025-26",
        "players": {
            "id": "p2",
            "name": "Nathan MacKinnon",
            "team": "COL",
            "position": "C",
        },
        "sources": {"name": "nhl_com", "display_name": "NHL.com"},
    },
    {
        "rank": 1,
        "season": "2025-26",
        "players": {
            "id": "p2",
            "name": "Nathan MacKinnon",
            "team": "COL",
            "position": "C",
        },
        "sources": {"name": "moneypuck", "display_name": "MoneyPuck"},
    },
    {
        "rank": 2,
        "season": "2025-26",
        "players": {
            "id": "p1",
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
        },
        "sources": {"name": "moneypuck", "display_name": "MoneyPuck"},
    },
]


# ---------------------------------------------------------------------------
# flatten_db_rankings
# ---------------------------------------------------------------------------


class TestFlattenDbRankings:
    def test_groups_by_source(self) -> None:
        result = flatten_db_rankings(TWO_SOURCE_ROWS)
        assert set(result.keys()) == {"nhl_com", "moneypuck"}

    def test_each_source_has_correct_player_count(self) -> None:
        result = flatten_db_rankings(TWO_SOURCE_ROWS)
        assert len(result["nhl_com"]) == 2
        assert len(result["moneypuck"]) == 2

    def test_player_entry_has_required_keys(self) -> None:
        result = flatten_db_rankings(TWO_SOURCE_ROWS)
        entry = result["nhl_com"][0]
        assert "player_id" in entry
        assert "name" in entry
        assert "rank" in entry

    def test_player_id_extracted_from_nested_players(self) -> None:
        result = flatten_db_rankings(TWO_SOURCE_ROWS)
        ids = {e["player_id"] for e in result["nhl_com"]}
        assert ids == {"p1", "p2"}

    def test_empty_input_returns_empty_dict(self) -> None:
        assert flatten_db_rankings([]) == {}

    def test_preserves_team_and_position(self) -> None:
        result = flatten_db_rankings(TWO_SOURCE_ROWS)
        mcd = next(e for e in result["nhl_com"] if e["player_id"] == "p1")
        assert mcd["team"] == "EDM"
        assert mcd["position"] == "C"


# ---------------------------------------------------------------------------
# compute_weighted_rankings
# ---------------------------------------------------------------------------


@pytest.fixture
def two_source_rankings() -> dict:
    return {
        "nhl_com": [
            {
                "player_id": "p1",
                "name": "McDavid",
                "team": "EDM",
                "position": "C",
                "rank": 1,
            },
            {
                "player_id": "p2",
                "name": "MacKinnon",
                "team": "COL",
                "position": "C",
                "rank": 2,
            },
            {
                "player_id": "p3",
                "name": "Draisaitl",
                "team": "EDM",
                "position": "C",
                "rank": 3,
            },
        ],
        "moneypuck": [
            {
                "player_id": "p2",
                "name": "MacKinnon",
                "team": "COL",
                "position": "C",
                "rank": 1,
            },
            {
                "player_id": "p1",
                "name": "McDavid",
                "team": "EDM",
                "position": "C",
                "rank": 2,
            },
            {
                "player_id": "p3",
                "name": "Draisaitl",
                "team": "EDM",
                "position": "C",
                "rank": 3,
            },
        ],
    }


class TestComputeWeightedRankings:
    def test_returns_all_players(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        assert len(result) == 3

    def test_assigns_composite_rank(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        ranks = [r["composite_rank"] for r in result]
        assert sorted(ranks) == [1, 2, 3]

    def test_rank_1_is_first(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        assert result[0]["composite_rank"] == 1

    def test_source_ranks_preserved(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        mcd = next(r for r in result if r["player_id"] == "p1")
        assert mcd["source_ranks"]["nhl_com"] == 1
        assert mcd["source_ranks"]["moneypuck"] == 2

    def test_composite_score_between_zero_and_one(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        for row in result:
            assert 0.0 <= row["composite_score"] <= 1.0

    def test_source_with_zero_weight_excluded(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 100, "moneypuck": 0})
        # Only nhl_com contributes; McDavid (rank 1) should be first
        assert result[0]["player_id"] == "p1"

    def test_source_absent_from_weights_excluded(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 100})
        # moneypuck not in weights → not counted
        mcd = next(r for r in result if r["player_id"] == "p1")
        assert "moneypuck" not in mcd["source_ranks"]

    def test_missing_source_degrades_gracefully(self) -> None:
        """Player only in one source still gets a composite score."""
        source_rankings = {
            "nhl_com": [
                {"player_id": "p1", "name": "McDavid", "rank": 1},
                {"player_id": "p2", "name": "MacKinnon", "rank": 2},
            ],
            "moneypuck": [
                # p2 not present
                {"player_id": "p1", "name": "McDavid", "rank": 1},
            ],
        }
        result = compute_weighted_rankings(source_rankings, {"nhl_com": 50, "moneypuck": 50})
        assert len(result) == 2
        p2 = next(r for r in result if r["player_id"] == "p2")
        assert p2["composite_score"] > 0

    def test_empty_source_rankings_returns_empty(self) -> None:
        assert compute_weighted_rankings({}, {"nhl_com": 50}) == []

    def test_sorted_descending_by_score(self, two_source_rankings: dict) -> None:
        result = compute_weighted_rankings(two_source_rankings, {"nhl_com": 50, "moneypuck": 50})
        scores = [r["composite_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_equal_weights_averages_ranks(self) -> None:
        """With equal weights, MacKinnon (#1 MoneyPuck, #2 NHL) and
        McDavid (#2 MoneyPuck, #1 NHL) should tie or rank by first-seen."""
        source_rankings = {
            "nhl_com": [
                {"player_id": "p1", "name": "McDavid", "rank": 1},
                {"player_id": "p2", "name": "MacKinnon", "rank": 2},
            ],
            "moneypuck": [
                {"player_id": "p2", "name": "MacKinnon", "rank": 1},
                {"player_id": "p1", "name": "McDavid", "rank": 2},
            ],
        }
        result = compute_weighted_rankings(source_rankings, {"nhl_com": 1, "moneypuck": 1})
        # Both players have symmetric ranks → composite scores should be equal
        scores = {r["player_id"]: r["composite_score"] for r in result}
        assert abs(scores["p1"] - scores["p2"]) < 1e-9

    def test_single_player_single_source(self) -> None:
        source_rankings = {
            "nhl_com": [{"player_id": "p1", "name": "McDavid", "rank": 1}],
        }
        result = compute_weighted_rankings(source_rankings, {"nhl_com": 1})
        assert len(result) == 1
        assert result[0]["composite_score"] == 1.0


class TestBuildCloseSnapshotFromRecipe:
    def test_builds_snapshot_using_persisted_recipe_inputs(self) -> None:
        recipe = {
            "season": "2026-27",
            "league_profile_id": "lp_1",
            "scoring_config_id": "sc_1",
            "source_weights": {"nhl_com": 1.0, "moneypuck": 1.0},
            "platform": "espn",
        }
        source_rankings = {
            "nhl_com": [
                {"player_id": "p1", "name": "McDavid", "rank": 1},
                {"player_id": "p2", "name": "MacKinnon", "rank": 2},
            ],
            "moneypuck": [
                {"player_id": "p2", "name": "MacKinnon", "rank": 1},
                {"player_id": "p1", "name": "McDavid", "rank": 2},
            ],
        }

        snapshot = build_close_snapshot_from_recipe(
            recipe=recipe,
            source_rankings=source_rankings,
            captured_at="2026-05-01T00:00:00+00:00",
        )

        assert snapshot["snapshot_version"] == 1
        assert snapshot["captured_at"] == "2026-05-01T00:00:00+00:00"
        assert snapshot["season"] == "2026-27"
        assert snapshot["league_profile_id"] == "lp_1"
        assert snapshot["scoring_config_id"] == "sc_1"
        assert snapshot["platform"] == "espn"
        assert snapshot["source_weights"] == {"nhl_com": 1.0, "moneypuck": 1.0}
        assert [row["player_id"] for row in snapshot["rankings"]] == ["p1", "p2"]

    def test_recomputes_from_source_rankings_not_cached_payload(self) -> None:
        recipe = {
            "season": "2026-27",
            "league_profile_id": "lp_1",
            "scoring_config_id": "sc_1",
            "source_weights": {"nhl_com": 1.0},
            "platform": "espn",
            "cached_rankings": [{"player_id": "stale", "composite_rank": 1}],
        }
        source_rankings = {
            "nhl_com": [
                {"player_id": "fresh", "name": "Fresh Player", "rank": 1},
            ]
        }

        snapshot = build_close_snapshot_from_recipe(
            recipe=recipe,
            source_rankings=source_rankings,
            captured_at="2026-05-01T00:00:00+00:00",
        )

        assert [row["player_id"] for row in snapshot["rankings"]] == ["fresh"]
