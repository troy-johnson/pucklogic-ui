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
    # With active_only=True:  table().select().eq().is_().order().execute()
    # With active_only=False: table().select().is_().order().execute()

    def _chain(self, mock_db: MagicMock) -> MagicMock:
        return (
            mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.execute.return_value
        )

    def _chain_no_filter(self, mock_db: MagicMock) -> MagicMock:
        return (
            mock_db.table.return_value.select.return_value.is_.return_value.order.return_value.execute.return_value
        )

    def test_queries_sources_table(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = []
        repo.list()
        mock_db.table.assert_called_once_with("sources")

    def test_filters_active_by_default(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = []
        repo.list(active_only=True)
        eq_call = mock_db.table.return_value.select.return_value.eq
        eq_call.assert_called_once_with("active", True)

    def test_excludes_custom_sources(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = []
        repo.list()
        is_call = mock_db.table.return_value.select.return_value.eq.return_value.is_
        is_call.assert_called_once_with("user_id", "null")

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

    def test_returns_source_when_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = NHL_SOURCE
        assert repo.get("s1") == NHL_SOURCE

    def test_returns_none_when_not_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
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

    def test_returns_source_when_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = NHL_SOURCE
        assert repo.get_by_name("nhl_com") == NHL_SOURCE

    def test_returns_none_when_not_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
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

    def test_returns_dict_keyed_by_name(self, repo: SourceRepository, mock_db: MagicMock) -> None:
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


class TestListCustom:
    def test_filters_by_user_id(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = []
        repo.list_custom(user_id="u1")
        mock_db.table.assert_called_with("sources")

    def test_returns_list(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = []
        result = repo.list_custom(user_id="u1")
        assert result == []

    def test_attaches_player_count(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        # First call: list sources
        list_chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        list_chain.execute.return_value.data = [
            {
                "id": "cs1",
                "name": "my_src",
                "display_name": "My Src",
                "user_id": "u1",
                "active": True,
                "created_at": "2026-03-17",
            }
        ]
        # Second call: count projections for the source
        count_chain = mock_db.table.return_value.select.return_value.eq.return_value
        count_chain.execute.return_value.count = 5
        count_chain.execute.return_value.data = []
        result = repo.list_custom(user_id="u1")
        assert "player_count" in result[0]


class TestGetSeasonsForSource:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        return (
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value
        )

    def test_returns_distinct_seasons(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        self._chain(mock_db).data = [
            {"season": "2025-26"},
            {"season": "2025-26"},  # duplicate — should be deduplicated
            {"season": "2024-25"},
        ]
        result = repo.get_seasons_for_source("src-1")
        assert result == ["2025-26", "2024-25"]

    def test_returns_empty_list_when_no_projections(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = []
        assert repo.get_seasons_for_source("src-1") == []

    def test_queries_player_projections_table(
        self, repo: SourceRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = []
        repo.get_seasons_for_source("src-1")
        mock_db.table.assert_called_with("player_projections")


class TestDeleteCustom:
    def test_returns_true_when_deleted(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = [{"id": "cs1"}]
        assert repo.delete_custom("cs1", "u1") is True

    def test_returns_false_when_not_found(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.data = []
        assert repo.delete_custom("cs1", "u1") is False


class TestCountCustom:
    def test_returns_count(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.count = 1
        assert repo.count_custom("u1") == 1

    def test_returns_zero_when_none(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value
        chain.execute.return_value.count = None
        assert repo.count_custom("u1") == 0


class TestUpsertCustom:
    def test_returns_source_id(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.upsert.return_value
        chain.execute.return_value.data = [{"id": "new-uuid"}]
        result = repo.upsert_custom("u1", "custom_u1_my_src", "My Src")
        assert result == "new-uuid"

    def test_calls_upsert_with_user_id(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.upsert.return_value
        chain.execute.return_value.data = [{"id": "x"}]
        repo.upsert_custom("u1", "custom_u1_my_src", "My Src")
        upsert_call = mock_db.table.return_value.upsert.call_args[0][0]
        assert upsert_call["user_id"] == "u1"

    def test_conflicts_on_name_only(self, repo: SourceRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.upsert.return_value
        chain.execute.return_value.data = [{"id": "x"}]
        repo.upsert_custom("u1", "custom_u1_my_src", "My Src")
        kwargs = mock_db.table.return_value.upsert.call_args[1]
        assert kwargs.get("on_conflict") == "name"
