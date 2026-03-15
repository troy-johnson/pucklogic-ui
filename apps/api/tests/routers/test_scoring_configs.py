from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_current_user, get_scoring_config_repository
from main import app

MOCK_USER = {"id": "u-1", "email": "test@example.com"}

PRESET_ROW = {
    "id": "sc-1",
    "name": "Standard Points",
    "stat_weights": {"g": 3, "a": 2, "ppp": 1},
    "is_preset": True,
}
CUSTOM_ROW = {
    "id": "sc-2",
    "name": "My Custom",
    "stat_weights": {"g": 5},
    "is_preset": False,
    "user_id": "u-1",
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = [PRESET_ROW]
    repo.create.return_value = CUSTOM_ROW
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_repo: MagicMock):
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_scoring_config_repository] = lambda: mock_repo
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestListScoringConfigs:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/scoring-configs").status_code == 200

    def test_returns_list(self, client: TestClient, mock_repo: MagicMock) -> None:
        mock_repo.list.return_value = [PRESET_ROW]
        data = client.get("/scoring-configs").json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_filters_by_user(self, client: TestClient, mock_repo: MagicMock) -> None:
        client.get("/scoring-configs")
        mock_repo.list.assert_called_once_with(user_id=MOCK_USER["id"])


class TestCreateScoringConfig:
    def test_returns_201(self, client: TestClient) -> None:
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        assert client.post("/scoring-configs", json=body).status_code == 201

    def test_ppp_ppg_double_count_returns_400(self, client: TestClient) -> None:
        body = {"name": "Bad", "stat_weights": {"ppp": 1, "ppg": 1}}
        resp = client.post("/scoring-configs", json=body)
        assert resp.status_code == 400
        assert "PPP" in resp.json()["detail"]

    def test_shp_shg_double_count_returns_400(self, client: TestClient) -> None:
        body = {"name": "Bad", "stat_weights": {"shp": 1, "shg": 1}}
        resp = client.post("/scoring-configs", json=body)
        assert resp.status_code == 400

    def test_valid_config_calls_create(self, client: TestClient, mock_repo: MagicMock) -> None:
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        client.post("/scoring-configs", json=body)
        mock_repo.create.assert_called_once()

    def test_sets_user_id_and_is_preset_false(self, client: TestClient, mock_repo: MagicMock) -> None:  # noqa: E501
        body = {"name": "My Custom", "stat_weights": {"g": 5}}
        client.post("/scoring-configs", json=body)
        call_data = mock_repo.create.call_args.args[0]
        assert call_data["user_id"] == MOCK_USER["id"]
        assert call_data["is_preset"] is False
