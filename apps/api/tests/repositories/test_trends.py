from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.trends import TrendsRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> TrendsRepository:
    return TrendsRepository(mock_db)


def _make_player(player_id: str = "p-1", name: str = "Player One") -> dict:
    return {"id": player_id, "name": name, "position": "C", "team": "EDM"}


def _make_trend(
    player_id: str = "p-1",
    season: str = "2025-26",
    breakout_score: float | None = 0.72,
    regression_risk: float | None = 0.15,
) -> dict:
    return {
        "player_id": player_id,
        "season": season,
        "breakout_score": breakout_score,
        "regression_risk": regression_risk,
        "confidence": 0.80,
        "shap_values": None,
        "shap_top3": None,
        "updated_at": "2026-08-01T08:00:00+00:00",
    }


def _configure(
    mock_db: MagicMock, players: list[dict], trends: list[dict]
) -> tuple[MagicMock, MagicMock]:
    """Wire mock_db for two independent .table().select()...execute() chains."""
    players_chain = MagicMock()
    players_chain.execute.return_value.data = players

    trends_chain = MagicMock()
    trends_chain.execute.return_value.data = trends

    def _table_side_effect(name: str) -> MagicMock:
        return players_chain if name == "players" else trends_chain

    mock_db.table.side_effect = _table_side_effect
    players_chain.select.return_value = players_chain
    players_chain.order.return_value = players_chain
    players_chain.range.return_value = players_chain

    trends_chain.select.return_value = trends_chain
    trends_chain.eq.return_value = trends_chain
    trends_chain.order.return_value = trends_chain
    trends_chain.range.return_value = trends_chain

    return players_chain, trends_chain


class TestGetTrends:
    def test_has_trends_false_when_no_rows(self, repo, mock_db):
        _configure(mock_db, players=[_make_player()], trends=[])
        result = repo.get_trends("2025-26")
        assert result.has_trends is False
        assert result.updated_at is None

    def test_has_trends_true_when_rows_exist(self, repo, mock_db):
        _configure(mock_db, players=[_make_player()], trends=[_make_trend()])
        result = repo.get_trends("2025-26")
        assert result.has_trends is True
        assert result.updated_at is not None

    def test_player_without_trends_has_null_scores(self, repo, mock_db):
        """Players with no player_trends row return null scores, not 500."""
        _configure(
            mock_db,
            players=[_make_player("p-1"), _make_player("p-2", "Player Two")],
            trends=[_make_trend("p-1")],  # p-2 has no trend row
        )
        result = repo.get_trends("2025-26")
        p2 = next(p for p in result.players if p.player_id == "p-2")
        assert p2.breakout_score is None
        assert p2.regression_risk is None

    def test_players_ordered_by_breakout_score_desc(self, repo, mock_db):
        """Players sorted breakout_score DESC, nulls last."""
        _configure(
            mock_db,
            players=[_make_player("p-1"), _make_player("p-2"), _make_player("p-3")],
            trends=[
                _make_trend("p-1", breakout_score=0.5),
                _make_trend("p-3", breakout_score=0.9),
                # p-2 has no trend row → null → last
            ],
        )
        result = repo.get_trends("2025-26")
        scores = [p.breakout_score for p in result.players]
        assert scores[0] == pytest.approx(0.9)
        assert scores[1] == pytest.approx(0.5)
        assert scores[2] is None

    def test_season_returned_in_response(self, repo, mock_db):
        _configure(mock_db, players=[], trends=[])
        result = repo.get_trends("2025-26")
        assert result.season == "2025-26"

    def test_legacy_wing_positions_are_normalized(self, repo, mock_db):
        _configure(
            mock_db,
            players=[
                {"id": "p-l", "name": "Left Wing", "position": "L", "team": "EDM"},
                {"id": "p-r", "name": "Right Wing", "position": "R", "team": "EDM"},
            ],
            trends=[],
        )
        result = repo.get_trends("2025-26")
        by_id = {p.player_id: p for p in result.players}
        assert by_id["p-l"].position == "LW"
        assert by_id["p-r"].position == "RW"

    def test_unknown_position_is_coerced_to_none(self, repo, mock_db):
        _configure(
            mock_db,
            players=[{"id": "p-f", "name": "Forward", "position": "F", "team": "EDM"}],
            trends=[],
        )
        result = repo.get_trends("2025-26")
        assert result.players[0].position is None

    def test_players_query_paginates_beyond_1000(self, repo, mock_db):
        players_chain, trends_chain = _configure(mock_db, players=[], trends=[])
        first = [_make_player(player_id=f"p-{i}") for i in range(1000)]
        second = [_make_player(player_id="p-1001")]
        players_chain.execute.side_effect = [MagicMock(data=first), MagicMock(data=second)]
        trends_chain.execute.return_value.data = []

        result = repo.get_trends("2025-26")

        assert result.player_count == 1001
        assert players_chain.execute.call_count == 2
