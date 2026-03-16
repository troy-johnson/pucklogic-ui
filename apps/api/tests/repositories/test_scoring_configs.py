from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.scoring_configs import ScoringConfigRepository

PRESET_ROW = {
    "id": "sc-1",
    "name": "Standard Points",
    "stat_weights": {"g": 3, "a": 2, "ppp": 1},
    "is_preset": True,
    "user_id": None,
    "created_at": "2026-03-01T00:00:00+00:00",
}
CUSTOM_ROW = {
    "id": "sc-2",
    "name": "My Custom",
    "stat_weights": {"g": 5, "a": 3},
    "is_preset": False,
    "user_id": "u-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> ScoringConfigRepository:
    return ScoringConfigRepository(mock_db)


class TestList:
    def test_queries_scoring_configs(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.or_.return_value.execute.return_value.data = []  # noqa: E501
        repo.list(user_id="u-1")
        mock_db.table.assert_called_once_with("scoring_configs")

    def test_returns_presets_and_user_configs(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.or_.return_value.execute.return_value.data = [  # noqa: E501
            PRESET_ROW, CUSTOM_ROW
        ]
        result = repo.list(user_id="u-1")
        assert len(result) == 2


class TestGet:
    def test_returns_config_when_found(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = PRESET_ROW  # noqa: E501
        result = repo.get("sc-1")
        assert result == PRESET_ROW

    def test_returns_none_when_not_found(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None  # noqa: E501
        assert repo.get("missing") is None

    def test_applies_ownership_filter_when_user_id_provided(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value
        chain.or_.return_value.maybe_single.return_value.execute.return_value.data = PRESET_ROW  # noqa: E501
        result = repo.get("sc-1", user_id="u-1")
        chain.or_.assert_called_once_with("is_preset.eq.true,user_id.eq.u-1")
        assert result == PRESET_ROW

    def test_no_ownership_filter_when_user_id_is_none(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        chain = mock_db.table.return_value.select.return_value.eq.return_value
        chain.maybe_single.return_value.execute.return_value.data = PRESET_ROW
        repo.get("sc-1", user_id=None)
        chain.or_.assert_not_called()


class TestCreate:
    def test_inserts_config(
        self, repo: ScoringConfigRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [CUSTOM_ROW]
        result = repo.create({
            "name": "My Custom",
            "stat_weights": {"g": 5},
            "is_preset": False,
            "user_id": "u-1",
        })
        assert result == CUSTOM_ROW
