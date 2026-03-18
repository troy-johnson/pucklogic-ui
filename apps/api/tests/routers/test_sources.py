"""Integration tests for GET /sources, GET /sources/custom, DELETE /sources/{id},
and POST /sources/upload."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_cache_service, get_current_user, get_source_repository
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

CUSTOM_SOURCE = {
    "id": "cs1",
    "name": "my_source",
    "display_name": "My Source",
    "user_id": "u1",
    "active": True,
    "is_paid": False,
    "player_count": 5,
    "season": "2025-26",
    "created_at": "2026-03-17T00:00:00",
}

AUTH_USER = {"id": "u1", "email": "user@test.com"}


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


class TestListCustomSources:
    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.list_custom.return_value = [CUSTOM_SOURCE]
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER

    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/sources/custom").status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        data = client.get("/sources/custom").json()
        assert isinstance(data, list)

    def test_calls_list_custom_with_user_id(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        client.get("/sources/custom")
        mock_source_repo.list_custom.assert_called_once_with(user_id="u1")

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        # Remove the auth override to get 401
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/sources/custom").status_code == 401


class TestDeleteSource:
    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.delete_custom.return_value = True
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        mock_cache = MagicMock()
        app.dependency_overrides[get_cache_service] = lambda: mock_cache

    def test_returns_204_on_success(self, client: TestClient) -> None:
        assert client.delete("/sources/cs1").status_code == 204

    def test_returns_404_when_not_found(
        self, client: TestClient, mock_source_repo: MagicMock
    ) -> None:
        mock_source_repo.delete_custom.return_value = False
        assert client.delete("/sources/cs1").status_code == 404

    def test_calls_invalidate_cache(self, client: TestClient, mock_source_repo: MagicMock) -> None:
        mock_cache = MagicMock()
        app.dependency_overrides[get_cache_service] = lambda: mock_cache
        client.delete("/sources/cs1")
        mock_cache.invalidate_rankings.assert_called_once()


class TestUploadSource:
    COLUMN_MAP = '{"Goals": "g", "Assists": "a", "GP": "gp"}'
    CSV_CONTENT = "Player,Goals,Assists,GP\nConnor McDavid,52,72,82\nUnknown Player,10,10,50"

    @pytest.fixture(autouse=True)
    def setup(self, mock_source_repo: MagicMock) -> None:
        mock_source_repo.count_custom.return_value = 0  # slots available
        mock_source_repo.upsert_custom.return_value = "src-new"
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER

        # Mock DB for player matching: table() returns different data per table name
        mock_db = MagicMock()

        def _table_side_effect(table_name: str) -> MagicMock:
            tbl = MagicMock()
            if table_name == "players":
                tbl.select.return_value.execute.return_value.data = [
                    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"}
                ]
            elif table_name == "player_aliases":
                tbl.select.return_value.execute.return_value.data = []
            else:
                tbl.select.return_value.execute.return_value.data = []
                tbl.upsert.return_value.execute.return_value.data = [{"id": "src-new"}]
            return tbl

        mock_db.table.side_effect = _table_side_effect
        from core.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        mock_cache = MagicMock()
        app.dependency_overrides[get_cache_service] = lambda: mock_cache

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={
                "source_name": "My Source",
                "season": "2025-26",
                "column_map": self.COLUMN_MAP,
            },
        )
        assert resp.status_code == 200

    def test_returns_upload_response_shape(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={
                "source_name": "My Source",
                "season": "2025-26",
                "column_map": self.COLUMN_MAP,
            },
        ).json()
        assert "source_id" in resp
        assert "rows_upserted" in resp
        assert "unmatched" in resp
        assert "slots_used" in resp

    def test_slot_limit_returns_400(self, client: TestClient, mock_source_repo: MagicMock) -> None:
        mock_source_repo.count_custom.return_value = 2  # already at limit
        resp = client.post(
            "/sources/upload",
            files={"file": ("proj.csv", io.BytesIO(self.CSV_CONTENT.encode()), "text/csv")},
            data={
                "source_name": "My Source",
                "season": "2025-26",
                "column_map": self.COLUMN_MAP,
            },
        )
        assert resp.status_code == 400
        assert "slot" in resp.json()["detail"].lower()

    def test_invalid_file_type_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/sources/upload",
            files={"file": ("bad.txt", io.BytesIO(b"not a csv"), "text/plain")},
            data={
                "source_name": "My Source",
                "season": "2025-26",
                "column_map": self.COLUMN_MAP,
            },
        )
        assert resp.status_code == 400

    def test_file_too_large_returns_400(self, client: TestClient) -> None:
        # 5MB + 1 byte: header + enough rows to exceed limit
        large_content = b"a,b\n" + b"x,y\n" * 1_400_000  # ~5.6 MB
        resp = client.post(
            "/sources/upload",
            files={"file": ("big.csv", io.BytesIO(large_content), "text/csv")},
            data={
                "source_name": "My Source",
                "season": "2025-26",
                "column_map": self.COLUMN_MAP,
            },
        )
        assert resp.status_code == 400
