from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.player_stats import PlayerStatsRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> PlayerStatsRepository:
    return PlayerStatsRepository(mock_db)


def _configure_db(mock_db: MagicMock, rows: list[dict]) -> None:
    """Wire mock_db so .table().select().in_().execute().data = rows."""
    (
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value
    ).data = rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_row(
    player_id: str = "p-mcdavid",
    season: int = 2025,
    toi_ev: float = 21.3,
    icf_per60: float | None = 14.2,
    ixg_per60: float | None = 12.0,
    date_of_birth: str = "1997-01-13",
    position: str = "C",
) -> dict:
    return {
        "player_id": player_id,
        "season": season,
        "toi_ev": toi_ev,
        "toi_pp": 3.5,
        "toi_sh": 0.2,
        "icf_per60": icf_per60,
        "ixg_per60": ixg_per60,
        "xgf_pct_5v5": 55.0,
        "cf_pct_adj": 54.0,
        "scf_per60": 18.0,
        "scf_pct": 53.0,
        "p1_per60": 3.5,
        "pdo": 1.010,
        "sh_pct": 0.115,
        "sh_pct_career_avg": 0.110,
        "g_minus_ixg": 0.5,
        "g_per60": 2.8,
        "oi_sh_pct": 0.095,
        "pp_unit": 1,
        "elc_flag": False,
        "contract_year_flag": False,
        "post_extension_flag": False,
        "players": {
            "date_of_birth": date_of_birth,
            "position": position,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSeasonsGrouped:
    def test_returns_dict_keyed_by_player_id(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-mcdavid", season=2025)])
        result = repo.get_seasons_grouped(season=2025)
        assert "p-mcdavid" in result

    def test_single_player_single_season_returns_one_row(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-mcdavid", season=2025)])
        result = repo.get_seasons_grouped(season=2025)
        assert len(result["p-mcdavid"]) == 1

    def test_multiple_seasons_sorted_newest_first(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        # DB returns in arbitrary order — repo must sort newest-first
        _configure_db(
            mock_db,
            [
                _make_db_row(player_id="p-mcdavid", season=2023),
                _make_db_row(player_id="p-mcdavid", season=2025),
                _make_db_row(player_id="p-mcdavid", season=2024),
            ],
        )
        result = repo.get_seasons_grouped(season=2025)
        seasons = [r["season"] for r in result["p-mcdavid"]]
        assert seasons == [2025, 2024, 2023]

    def test_multiple_players_each_grouped_separately(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(
            mock_db,
            [
                _make_db_row(player_id="p-mcdavid", season=2025),
                _make_db_row(player_id="p-draisaitl", season=2025),
            ],
        )
        result = repo.get_seasons_grouped(season=2025)
        assert "p-mcdavid" in result
        assert "p-draisaitl" in result
        assert len(result["p-mcdavid"]) == 1
        assert len(result["p-draisaitl"]) == 1

    def test_player_with_one_season_returns_one_row(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [_make_db_row(player_id="p-rookie", season=2025)])
        result = repo.get_seasons_grouped(season=2025, window=3)
        assert len(result["p-rookie"]) == 1

    def test_players_join_flattened_into_row(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(
            mock_db,
            [
                _make_db_row(
                    player_id="p-mcdavid", season=2025, date_of_birth="1997-01-13", position="C"
                )
            ],
        )
        result = repo.get_seasons_grouped(season=2025)
        row = result["p-mcdavid"][0]
        assert row["date_of_birth"] == "1997-01-13"
        assert row["position"] == "C"
        assert "players" not in row  # nested dict should be flattened

    def test_queries_correct_season_range(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [])
        repo.get_seasons_grouped(season=2025, window=3)
        # The .in_() call should receive seasons [2023, 2024, 2025]
        in_call_args = mock_db.table.return_value.select.return_value.in_.call_args
        field, seasons = in_call_args[0]
        assert field == "season"
        assert set(seasons) == {2023, 2024, 2025}

    def test_custom_window_queries_correct_seasons(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [])
        repo.get_seasons_grouped(season=2025, window=2)
        in_call_args = mock_db.table.return_value.select.return_value.in_.call_args
        _, seasons = in_call_args[0]
        assert set(seasons) == {2024, 2025}

    def test_empty_result_returns_empty_dict(
        self, repo: PlayerStatsRepository, mock_db: MagicMock
    ) -> None:
        _configure_db(mock_db, [])
        result = repo.get_seasons_grouped(season=2025)
        assert result == {}
