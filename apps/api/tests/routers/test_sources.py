"""Integration tests for GET /sources."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_source_repository
from main import app

NHL_SOURCE = {
    "id": "s1",
    "name": "nhl_com",
    "display_name": "NHL.com",
    "url": "https://nhl.com",
    "active": True,
}
MP_SOURCE = {
    "id": "s2",
    "name": "moneypuck",
    "display_name": "MoneyPuck",
    "url": None,
    "active": True,
}


@pytest.fixture
def mock_source_repo() -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = [NHL_SOURCE, MP_SOURCE]
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_source_repo: MagicMock) -> None:
    app.dependency_overrides[get_source_repository] = lambda: mock_source_repo
    yield
    app.dependency_overrides.clear()


class TestListSources:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/sources").status_code == 200

    def test_returns_list_of_sources(self, client: TestClient) -> None:
        data = client.get("/sources").json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_source_has_required_fields(self, client: TestClient) -> None:
        source = client.get("/sources").json()[0]
        assert "id" in source
        assert "name" in source
        assert "display_name" in source
        assert "active" in source

    def test_active_only_param_passed_to_repo(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        client.get("/sources?active_only=false")
        mock_source_repo.list.assert_called_once_with(active_only=False)

    def test_active_only_defaults_to_true(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        client.get("/sources")
        mock_source_repo.list.assert_called_once_with(active_only=True)
