from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
from core.dependencies import get_current_user, get_league_profile_repository

MOCK_USER = {"id": "u-1", "email": "test@example.com"}
PROFILE_ROW = {
    "id": "lp-1",
    "user_id": "u-1",
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2},
    "scoring_config_id": "sc-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}
CREATE_BODY = {
    "name": "My ESPN League",
    "platform": "espn",
    "num_teams": 12,
    "roster_slots": {"C": 2},
    "scoring_config_id": "sc-1",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_league_profile_repository] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListLeagueProfiles:
    def test_returns_200(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = [PROFILE_ROW]
        assert client.get("/league-profiles").status_code == 200

    def test_returns_list(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = [PROFILE_ROW]
        data = client.get("/league-profiles").json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_filters_by_user(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.list.return_value = []
        client.get("/league-profiles")
        mock_db.list.assert_called_once_with(user_id=MOCK_USER["id"])


class TestCreateLeagueProfile:
    def test_returns_201(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.create.return_value = PROFILE_ROW
        assert client.post("/league-profiles", json=CREATE_BODY).status_code == 201

    def test_creates_with_user_id(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.create.return_value = PROFILE_ROW
        client.post("/league-profiles", json=CREATE_BODY)
        call_data = mock_db.create.call_args.args[0]
        assert call_data["user_id"] == MOCK_USER["id"]

    def test_missing_name_returns_422(self, client: TestClient) -> None:
        body = {k: v for k, v in CREATE_BODY.items() if k != "name"}
        assert client.post("/league-profiles", json=body).status_code == 422

    def test_invalid_platform_returns_422(self, client: TestClient) -> None:
        assert client.post(
            "/league-profiles", json={**CREATE_BODY, "platform": "sleeper"}
        ).status_code == 422
