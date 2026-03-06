"""Integration tests for POST /rankings/compute."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_cache_service, get_rankings_repository
from main import app

SEASON = "2025-26"
WEIGHTS = {"nhl_com": 50.0, "moneypuck": 50.0}

CACHED_RANKINGS = [
    {
        "composite_rank": 1,
        "composite_score": 0.9,
        "player_id": "p1",
        "name": "McDavid",
        "team": "EDM",
        "position": "C",
        "source_ranks": {"nhl_com": 1, "moneypuck": 2},
    }
]

DB_ROWS = [
    {
        "rank": 1,
        "season": SEASON,
        "players": {"id": "p1", "name": "McDavid", "team": "EDM", "position": "C"},
        "sources": {"name": "nhl_com", "display_name": "NHL.com"},
    },
    {
        "rank": 1,
        "season": SEASON,
        "players": {"id": "p1", "name": "McDavid", "team": "EDM", "position": "C"},
        "sources": {"name": "moneypuck", "display_name": "MoneyPuck"},
    },
]

VALID_BODY = {"season": SEASON, "weights": WEIGHTS}


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_season.return_value = DB_ROWS
    return repo


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get_rankings.return_value = None  # default: cache miss
    return cache


@pytest.fixture(autouse=True)
def override_deps(mock_repo: MagicMock, mock_cache: MagicMock) -> None:
    app.dependency_overrides[get_rankings_repository] = lambda: mock_repo
    app.dependency_overrides[get_cache_service] = lambda: mock_cache
    yield
    app.dependency_overrides.clear()


class TestComputeRankings:
    def test_returns_200_on_cache_miss(self, client: TestClient) -> None:
        assert client.post("/rankings/compute", json=VALID_BODY).status_code == 200

    def test_response_has_required_fields(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert "season" in data
        assert "computed_at" in data
        assert "cached" in data
        assert "rankings" in data

    def test_season_echoed_in_response(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["season"] == SEASON

    def test_cached_false_on_cache_miss(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["cached"] is False

    def test_cache_is_populated_on_miss(
        self, client: TestClient, mock_cache: MagicMock
    ) -> None:
        client.post("/rankings/compute", json=VALID_BODY)
        mock_cache.set_rankings.assert_called_once()

    def test_repo_is_called_on_cache_miss(
        self, client: TestClient, mock_repo: MagicMock
    ) -> None:
        client.post("/rankings/compute", json=VALID_BODY)
        mock_repo.get_by_season.assert_called_once_with(SEASON)

    def test_cached_true_on_cache_hit(
        self, client: TestClient, mock_cache: MagicMock
    ) -> None:
        mock_cache.get_rankings.return_value = CACHED_RANKINGS
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert data["cached"] is True

    def test_repo_not_called_on_cache_hit(
        self, client: TestClient, mock_cache: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_cache.get_rankings.return_value = CACHED_RANKINGS
        client.post("/rankings/compute", json=VALID_BODY)
        mock_repo.get_by_season.assert_not_called()

    def test_rankings_list_in_response(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        assert isinstance(data["rankings"], list)
        assert len(data["rankings"]) > 0

    def test_ranked_player_has_required_fields(self, client: TestClient) -> None:
        data = client.post("/rankings/compute", json=VALID_BODY).json()
        player = data["rankings"][0]
        assert "composite_rank" in player
        assert "composite_score" in player
        assert "player_id" in player
        assert "name" in player

    def test_missing_season_returns_422(self, client: TestClient) -> None:
        assert client.post("/rankings/compute", json={"weights": WEIGHTS}).status_code == 422

    def test_missing_weights_returns_422(self, client: TestClient) -> None:
        assert client.post("/rankings/compute", json={"season": SEASON}).status_code == 422
