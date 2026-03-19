from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.league_profiles import LeagueProfileRepository

PROFILE_ROW = {
    "id": "lp-1",
    "user_id": "u-1",
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2, "LW": 2, "RW": 2, "D": 4, "G": 2},
    "scoring_config_id": "sc-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> LeagueProfileRepository:
    return LeagueProfileRepository(mock_db)


class TestList:
    def test_queries_league_profiles(
        self, repo: LeagueProfileRepository, mock_db: MagicMock
    ) -> None:  # noqa: E501
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []  # noqa: E501
        repo.list(user_id="u-1")
        mock_db.table.assert_called_once_with("league_profiles")

    def test_filters_by_user_id(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.execute.return_value.data = []
        repo.list(user_id="u-1")
        chain.assert_called_once_with("user_id", "u-1")

    def test_returns_profiles(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            PROFILE_ROW
        ]  # noqa: E501
        assert repo.list("u-1") == [PROFILE_ROW]


class TestCreate:
    def test_inserts_profile(self, repo: LeagueProfileRepository, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [PROFILE_ROW]
        result = repo.create(
            {
                "user_id": "u-1",
                "name": "My ESPN League",
                "platform": "espn",
                "num_teams": 12,
                "roster_slots": {},
                "scoring_config_id": "sc-1",
            }
        )
        mock_db.table.assert_called_once_with("league_profiles")
        assert result == PROFILE_ROW

    def test_inserts_correct_user_id(
        self, repo: LeagueProfileRepository, mock_db: MagicMock
    ) -> None:  # noqa: E501
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [PROFILE_ROW]
        repo.create(
            {
                "user_id": "u-1",
                "name": "x",
                "platform": "espn",
                "num_teams": 10,
                "roster_slots": {},
                "scoring_config_id": "sc-1",
            }
        )  # noqa: E501
        insert_arg = mock_db.table.return_value.insert.call_args.args[0]
        assert insert_arg["user_id"] == "u-1"


class TestGet:
    def test_returns_profile_when_found(
        self, repo: LeagueProfileRepository, mock_db: MagicMock
    ) -> None:  # noqa: E501
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [  # noqa: E501
            PROFILE_ROW
        ]
        result = repo.get(profile_id="lp-1", user_id="u-1")
        assert result == PROFILE_ROW

    def test_returns_none_when_not_found(
        self, repo: LeagueProfileRepository, mock_db: MagicMock
    ) -> None:  # noqa: E501
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []  # noqa: E501
        assert repo.get("lp-1", "u-1") is None
