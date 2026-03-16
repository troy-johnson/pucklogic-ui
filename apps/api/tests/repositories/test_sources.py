"""Unit tests for SourceRepository."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.sources import SourceRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> SourceRepository:
    return SourceRepository(mock_db)


NHL_SOURCE = {"id": "s1", "name": "nhl_com", "display_name": "NHL.com", "active": True}
MP_SOURCE = {
    "id": "s2",
    "name": "moneypuck",
    "display_name": "MoneyPuck",
    "active": True,
}


class TestList:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.eq.return_value
        return chain.order.return_value.execute.return_value

    def _chain_no_filter(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value
        return chain.order.return_value.execute.return_value

    def test_queries_sources_table(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = []
        repo.list()
        mock_db.table.assert_called_once_with("sources")

    def test_filters_active_by_default(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.order.return_value.execute.return_value.data = []
        repo.list(active_only=True)
        chain.assert_called_once_with("active", True)

    def test_returns_all_when_active_only_false(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain_no_filter(mock_db).data = [NHL_SOURCE, MP_SOURCE]
        result = repo.list(active_only=False)
        assert result == [NHL_SOURCE, MP_SOURCE]

    def test_returns_data(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = [NHL_SOURCE]
        assert repo.list() == [NHL_SOURCE]


class TestGet:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.eq.return_value
        return chain.maybe_single.return_value.execute.return_value

    def test_returns_source_when_found(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = NHL_SOURCE
        assert repo.get("s1") == NHL_SOURCE

    def test_returns_none_when_not_found(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = None
        assert repo.get("nonexistent") is None

    def test_filters_by_id(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.maybe_single.return_value.execute.return_value.data = None
        repo.get("s99")
        chain.assert_called_once_with("id", "s99")


class TestGetByName:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.eq.return_value
        return chain.maybe_single.return_value.execute.return_value

    def test_returns_source_when_found(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = NHL_SOURCE
        assert repo.get_by_name("nhl_com") == NHL_SOURCE

    def test_returns_none_when_not_found(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = None
        assert repo.get_by_name("unknown") is None

    def test_filters_by_name(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.maybe_single.return_value.execute.return_value.data = None
        repo.get_by_name("nhl_com")
        chain.assert_called_once_with("name", "nhl_com")


class TestGetByNames:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.in_.return_value
        return chain.execute.return_value

    def test_returns_dict_keyed_by_name(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = [NHL_SOURCE, MP_SOURCE]
        result = repo.get_by_names(["nhl_com", "moneypuck"])
        assert result == {"nhl_com": NHL_SOURCE, "moneypuck": MP_SOURCE}

    def test_missing_name_absent_from_result(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = [NHL_SOURCE]
        result = repo.get_by_names(["nhl_com", "unknown"])
        assert "unknown" not in result
        assert "nhl_com" in result

    def test_empty_names_returns_empty_dict(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        result = repo.get_by_names([])
        assert result == {}
        mock_db.table.assert_not_called()

    def test_uses_in_filter(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = []
        repo.get_by_names(["nhl_com"])
        mock_db.table.return_value.select.return_value.in_.assert_called_once_with(
            "name", ["nhl_com"]
        )
