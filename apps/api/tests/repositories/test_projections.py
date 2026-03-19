from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.projections import ProjectionRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> ProjectionRepository:
    return ProjectionRepository(mock_db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_row(
    player_id: str = "p1",
    source_name: str = "dobber",
    is_paid: bool = False,
    source_user_id: str | None = None,
    g: int | None = 30,
) -> dict:
    return {
        "player_id": player_id,
        "season": "2025-26",
        "g": g,
        "a": None,
        "plus_minus": None,
        "pim": None,
        "ppg": None,
        "ppa": None,
        "ppp": None,
        "shg": None,
        "sha": None,
        "shp": None,
        "sog": None,
        "fow": None,
        "fol": None,
        "hits": None,
        "blocks": None,
        "gp": None,
        "gs": None,
        "w": None,
        "l": None,
        "ga": None,
        "sa": None,
        "sv": None,
        "sv_pct": None,
        "so": None,
        "otl": None,
        "sources": {
            "name": source_name,
            "default_weight": 1.0,
            "is_paid": is_paid,
            "user_id": source_user_id,
        },
        "players": {
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
        },
        "player_platform_positions": [{"platform": "espn", "positions": ["C"]}],
        "schedule_scores": [{"season": "2025-26", "schedule_score": 0.8, "off_night_games": 24}],
    }


class TestGetBySeason:
    def test_queries_player_projections_table(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []  # noqa: E501
        repo.get_by_season("2025-26", "espn", "user-1")
        mock_db.table.assert_called_once_with("player_projections")

    def test_filters_by_season(self, repo: ProjectionRepository, mock_db: MagicMock) -> None:
        chain = mock_db.table.return_value.select.return_value.eq
        chain.return_value.execute.return_value.data = []
        repo.get_by_season("2025-26", "espn", "user-1")
        chain.assert_called_once_with("season", "2025-26")

    def test_returns_rows(self, repo: ProjectionRepository, mock_db: MagicMock) -> None:
        row = _make_db_row()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            row
        ]  # noqa: E501
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert len(result) == 1

    def test_returns_empty_list_when_no_data(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []  # noqa: E501
        assert repo.get_by_season("2025-26", "espn", "user-1") == []

    def test_excludes_other_users_custom_sources(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        # System source (user_id=None) and requesting user's own source are kept.
        # Another user's custom source must be excluded by the privacy filter.
        system_row = _make_db_row("p1", source_user_id=None)
        own_row = _make_db_row("p2", source_user_id="user-1")
        other_row = _make_db_row("p3", source_user_id="user-99")
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            system_row,
            own_row,
            other_row,
        ]
        result = repo.get_by_season("2025-26", "espn", "user-1")
        player_ids = [r["player_id"] for r in result]
        assert "p1" in player_ids  # system source — visible
        assert "p2" in player_ids  # own custom source — visible
        assert "p3" not in player_ids  # another user's source — excluded

    def test_filters_platform_positions_to_requested_platform(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        row = _make_db_row("p1")
        # Row has both espn and yahoo platform entries
        row["player_platform_positions"] = [
            {"platform": "espn", "positions": ["C"]},
            {"platform": "yahoo", "positions": ["C", "F"]},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            row
        ]  # noqa: E501
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert len(result) == 1
        # Only the espn entry should remain
        assert result[0]["player_platform_positions"] == [{"platform": "espn", "positions": ["C"]}]

    def test_non_matching_platform_positions_filtered_out(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        row = _make_db_row("p1")
        row["player_platform_positions"] = [{"platform": "yahoo", "positions": ["C"]}]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            row
        ]  # noqa: E501
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert len(result) == 1
        assert result[0]["player_platform_positions"] == []

    def test_filters_schedule_scores_to_requested_season(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        row = _make_db_row("p1")
        row["schedule_scores"] = [
            {"season": "2025-26", "schedule_score": 0.8, "off_night_games": 24},
            {"season": "2024-25", "schedule_score": 0.5, "off_night_games": 10},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            row
        ]  # noqa: E501
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert len(result) == 1
        assert result[0]["schedule_scores"] == [
            {"season": "2025-26", "schedule_score": 0.8, "off_night_games": 24}
        ]

    def test_wrong_season_schedule_scores_filtered_out(
        self, repo: ProjectionRepository, mock_db: MagicMock
    ) -> None:
        row = _make_db_row("p1")
        row["schedule_scores"] = [
            {"season": "2024-25", "schedule_score": 0.5, "off_night_games": 5}
        ]  # noqa: E501
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            row
        ]  # noqa: E501
        result = repo.get_by_season("2025-26", "espn", "user-1")
        assert result[0]["schedule_scores"] == []
