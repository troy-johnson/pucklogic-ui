"""Integration tests for GET /players and GET /players/{id}."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_player_repository
from main import app

PLAYER_1 = {
    "id": "p1",
    "name": "Connor McDavid",
    "team": "EDM",
    "position": "C",
    "nhl_id": 8478402,
}
PLAYER_2 = {
    "id": "p2",
    "name": "Nathan MacKinnon",
    "team": "COL",
    "position": "C",
    "nhl_id": 8477492,
}


@pytest.fixture
def mock_player_repo() -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = [PLAYER_1, PLAYER_2]
    repo.get.return_value = PLAYER_1
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_player_repo: MagicMock) -> None:
    app.dependency_overrides[get_player_repository] = lambda: mock_player_repo
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /players
# ---------------------------------------------------------------------------


class TestListPlayers:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/players").status_code == 200

    def test_returns_list_of_players(self, client: TestClient) -> None:
        data = client.get("/players").json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_player_has_required_fields(self, client: TestClient) -> None:
        player = client.get("/players").json()[0]
        assert player["id"] == "p1"
        assert player["name"] == "Connor McDavid"
        assert player["team"] == "EDM"
        assert player["position"] == "C"

    def test_default_pagination_params_passed_to_repo(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        client.get("/players")
        mock_player_repo.list.assert_called_once_with(limit=100, offset=0)

    def test_custom_pagination_params_passed_to_repo(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        client.get("/players?limit=50&offset=100")
        mock_player_repo.list.assert_called_once_with(limit=50, offset=100)

    def test_limit_out_of_range_returns_422(self, client: TestClient) -> None:
        assert client.get("/players?limit=0").status_code == 422
        assert client.get("/players?limit=501").status_code == 422

    def test_negative_offset_returns_422(self, client: TestClient) -> None:
        assert client.get("/players?offset=-1").status_code == 422


# ---------------------------------------------------------------------------
# GET /players/{player_id}
# ---------------------------------------------------------------------------


class TestGetPlayer:
    def test_returns_200_for_existing_player(self, client: TestClient) -> None:
        assert client.get("/players/p1").status_code == 200

    def test_returns_player_data(self, client: TestClient) -> None:
        data = client.get("/players/p1").json()
        assert data["id"] == "p1"
        assert data["name"] == "Connor McDavid"

    def test_returns_404_for_unknown_player(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        mock_player_repo.get.return_value = None
        assert client.get("/players/unknown-id").status_code == 404

    def test_404_detail_message(
        self, client: TestClient, mock_player_repo: MagicMock
    ) -> None:
        mock_player_repo.get.return_value = None
        resp = client.get("/players/unknown-id")
        assert resp.json()["detail"] == "Player not found"
