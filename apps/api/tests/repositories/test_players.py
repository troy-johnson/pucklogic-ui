from unittest.mock import MagicMock

import pytest

from repositories import PlayerRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> PlayerRepository:
    return PlayerRepository(mock_db)


class TestList:
    def _list_data(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.range.return_value
        return chain.execute.return_value

    def test_queries_players_table(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        self._list_data(mock_db).data = []
        repo.list()
        mock_db.table.assert_called_once_with("players")

    def test_returns_data(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
        player = {"id": "p1", "name": "Connor McDavid"}
        self._list_data(mock_db).data = [player]
        assert repo.list() == [player]

    def test_returns_empty_list_when_no_players(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        self._list_data(mock_db).data = []
        assert repo.list() == []


class TestGet:
    def test_returns_player_when_found(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        player = {"id": "p1", "name": "Connor McDavid"}
        (
            mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
        ) = player
        assert repo.get("p1") == player

    def test_returns_none_when_not_found(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
        ) = None
        assert repo.get("nonexistent") is None

    def test_filters_by_id(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.maybe_single.return_value.execute.return_value.data = None
        repo.get("p99")
        chain.assert_called_once_with("id", "p99")
