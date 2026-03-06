"""Unit tests for RankingsRepository."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.rankings import RankingsRepository

SEASON = "2025-26"

MOCK_ROW = {
    "rank": 1,
    "season": SEASON,
    "players": {"id": "p1", "name": "Connor McDavid", "team": "EDM", "position": "C"},
    "sources": {"name": "nhl_com", "display_name": "NHL.com"},
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> RankingsRepository:
    return RankingsRepository(mock_db)


class TestGetBySeason:
    def _base_chain(self, mock_db: MagicMock) -> MagicMock:
        return (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value
        )

    def test_queries_player_rankings_table(
        self, repo: RankingsRepository, mock_db: MagicMock
    ) -> None:
        self._base_chain(mock_db).data = []
        repo.get_by_season(SEASON)
        mock_db.table.assert_called_once_with("player_rankings")

    def test_filters_by_season(self, repo: RankingsRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.execute.return_value.data = []
        repo.get_by_season(SEASON)
        chain.assert_called_once_with("season", SEASON)

    def test_returns_data(self, repo: RankingsRepository, mock_db: MagicMock) -> None:
        self._base_chain(mock_db).data = [MOCK_ROW]
        result = repo.get_by_season(SEASON)
        assert result == [MOCK_ROW]

    def test_returns_empty_list_when_no_data(
        self, repo: RankingsRepository, mock_db: MagicMock
    ) -> None:
        self._base_chain(mock_db).data = []
        assert repo.get_by_season(SEASON) == []

    def test_filters_by_source_names_when_provided(
        self, repo: RankingsRepository, mock_db: MagicMock
    ) -> None:
        """When source_names is given, an extra .in_() filter is applied."""
        in_chain = mock_db.table.return_value.select.return_value.eq.return_value.in_
        in_chain.return_value.execute.return_value.data = [MOCK_ROW]
        result = repo.get_by_season(SEASON, source_names=["nhl_com"])
        in_chain.assert_called_once_with("sources.name", ["nhl_com"])
        assert result == [MOCK_ROW]


class TestGetSourcesForSeason:
    def test_returns_distinct_source_names(
        self, repo: RankingsRepository, mock_db: MagicMock
    ) -> None:
        raw = [
            {"sources": {"name": "nhl_com"}},
            {"sources": {"name": "moneypuck"}},
            {"sources": {"name": "nhl_com"}},  # duplicate — should be deduplicated
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value
            .data
        ) = raw
        result = repo.get_sources_for_season(SEASON)
        assert result == ["nhl_com", "moneypuck"]

    def test_returns_empty_when_no_data(
        self, repo: RankingsRepository, mock_db: MagicMock
    ) -> None:
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value
            .data
        ) = []
        assert repo.get_sources_for_season(SEASON) == []
