from unittest.mock import MagicMock

import pytest

from repositories.players import PlayerRepository


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

    def test_queries_players_table(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
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

    def test_passes_pagination_range_to_supabase(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        self._list_data(mock_db).data = []
        repo.list(limit=25, offset=50)
        range_call = mock_db.table.return_value.select.return_value.range
        range_call.assert_called_once_with(50, 74)  # offset, offset + limit - 1

    def test_default_pagination_uses_limit_100_offset_0(
        self, repo: PlayerRepository, mock_db: MagicMock
    ) -> None:
        self._list_data(mock_db).data = []
        repo.list()
        range_call = mock_db.table.return_value.select.return_value.range
        range_call.assert_called_once_with(0, 99)  # default: offset=0, limit=100


class TestGet:
    def test_returns_player_when_found(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
        player = {"id": "p1", "name": "Connor McDavid"}
        (
            mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
        ) = player
        assert repo.get("p1") == player

    def test_returns_none_when_not_found(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
        ) = None
        assert repo.get("nonexistent") is None

    def test_filters_by_id(self, repo: PlayerRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.maybe_single.return_value.execute.return_value.data = None
        repo.get("p99")
        chain.assert_called_once_with("id", "p99")
