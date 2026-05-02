"""Integration tests for GET/POST/DELETE /user-kits."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_current_user, get_db, get_subscription_repository
from main import app

MOCK_USER = {"id": "user-123", "email": "test@example.com"}

KIT_ROW = {
    "id": "kit-1",
    "name": "My Kit",
    "source_weights": {"nhl_com": 50.0, "moneypuck": 50.0},
    "created_at": "2026-03-01T00:00:00+00:00",
}


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    repo = MagicMock()
    repo.is_active.return_value = True
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_db: MagicMock, mock_sub_repo: MagicMock) -> None:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_subscription_repository] = lambda: mock_sub_repo
    yield
    app.dependency_overrides.clear()


class TestListUserKits:
    def test_returns_200(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
        ) = [KIT_ROW]
        assert client.get("/user-kits").status_code == 200

    def test_returns_list_of_kits(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
        ) = [KIT_ROW]
        data = client.get("/user-kits").json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_kit_has_required_fields(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
        ) = [KIT_ROW]
        kit = client.get("/user-kits").json()[0]
        assert "id" in kit
        assert "name" in kit
        assert "source_weights" in kit
        assert "created_at" in kit

    def test_filters_by_user_id(self, client: TestClient, mock_db: MagicMock) -> None:
        eq_chain = mock_db.table.return_value.select.return_value.eq
        eq_chain.return_value.order.return_value.execute.return_value.data = []
        client.get("/user-kits")
        eq_chain.assert_called_once_with("user_id", MOCK_USER["id"])

    def test_returns_empty_list_when_no_kits(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data
        ) = []
        assert client.get("/user-kits").json() == []


class TestCreateUserKit:
    CREATE_BODY = {
        "name": "My Kit",
        "source_weights": {"nhl_com": 60.0, "moneypuck": 40.0},
    }

    def test_returns_201(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [KIT_ROW]
        assert client.post("/user-kits", json=self.CREATE_BODY).status_code == 201

    def test_returns_created_kit(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [KIT_ROW]
        data = client.post("/user-kits", json=self.CREATE_BODY).json()
        assert data["id"] == KIT_ROW["id"]
        assert data["name"] == KIT_ROW["name"]

    def test_inserts_with_user_id(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [KIT_ROW]
        client.post("/user-kits", json=self.CREATE_BODY)
        insert_call = mock_db.table.return_value.insert.call_args.args[0]
        assert insert_call["user_id"] == MOCK_USER["id"]

    def test_inserts_source_weights(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [KIT_ROW]
        client.post("/user-kits", json=self.CREATE_BODY)
        insert_call = mock_db.table.return_value.insert.call_args.args[0]
        assert insert_call["source_weights"] == self.CREATE_BODY["source_weights"]
        assert "season" not in insert_call

    def test_returns_500_when_insert_fails(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = []
        assert client.post("/user-kits", json=self.CREATE_BODY).status_code == 500

    def test_missing_name_returns_422(self, client: TestClient) -> None:
        body = {"source_weights": {"nhl_com": 50}}
        assert client.post("/user-kits", json=body).status_code == 422

    def test_returns_403_when_user_lacks_active_kit_pass(
        self,
        client: TestClient,
        mock_db: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [KIT_ROW]
        mock_sub_repo.is_active.return_value = False

        resp = client.post("/user-kits", json=self.CREATE_BODY)

        assert resp.status_code == 403
        assert resp.json()["detail"] == "active draft pass required"


class TestDeleteUserKit:
    def test_returns_204_when_deleted(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data
        ) = [KIT_ROW]
        assert client.delete("/user-kits/kit-1").status_code == 204

    def test_returns_404_when_not_found(self, client: TestClient, mock_db: MagicMock) -> None:
        (
            mock_db.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data
        ) = []
        assert client.delete("/user-kits/nonexistent").status_code == 404

    def test_filters_by_user_id_on_delete(self, client: TestClient, mock_db: MagicMock) -> None:
        """Ensures a user can only delete their own kits."""
        delete_chain = mock_db.table.return_value.delete.return_value
        eq1 = delete_chain.eq
        eq2 = eq1.return_value.eq
        eq2.return_value.execute.return_value.data = [KIT_ROW]

        client.delete("/user-kits/kit-1")

        # First eq: kit_id, second eq: user_id
        eq2.assert_called_once_with("user_id", MOCK_USER["id"])

    def test_returns_403_when_user_lacks_active_kit_pass(
        self,
        client: TestClient,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_sub_repo.is_active.return_value = False

        resp = client.delete("/user-kits/kit-1")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "active draft pass required"


class TestUnauthenticated:
    def test_list_returns_401_without_auth(self, client: TestClient) -> None:
        from fastapi import HTTPException as _HTTPException

        def _raise_401() -> None:
            raise _HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        app.dependency_overrides[get_current_user] = _raise_401
        try:
            resp = client.get("/user-kits")
            assert resp.status_code == 401
        finally:
            # Restore the autouse fixture overrides for subsequent tests
            app.dependency_overrides[get_current_user] = lambda: MOCK_USER
