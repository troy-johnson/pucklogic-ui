"""Integration tests for /auth endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_current_user
from main import app

MOCK_USER = {"id": "user-abc", "email": "test@example.com", "token": "jwt-token"}


def _mock_supabase_auth_resp(
    access_token: str = "access123", refresh_token: str = "refresh123"
) -> MagicMock:
    resp = MagicMock()
    resp.session.access_token = access_token
    resp.session.refresh_token = refresh_token
    resp.user.id = "user-abc"
    resp.user.email = "test@example.com"
    return resp


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_success_returns_200_with_tokens(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.sign_up.return_value = _mock_supabase_auth_resp()
            resp = client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "securepass1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "access123"
        assert data["refresh_token"] == "refresh123"
        assert data["user"]["email"] == "test@example.com"

    def test_email_confirmation_path_returns_202(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            no_session = MagicMock()
            no_session.session = None
            mock_db.return_value.auth.sign_up.return_value = no_session
            resp = client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "securepass1"},
            )
        assert resp.status_code == 202
        assert "message" in resp.json()

    def test_duplicate_email_returns_400(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.sign_up.side_effect = Exception(
                "User already registered"
            )
            resp = client.post(
                "/auth/register",
                json={"email": "existing@example.com", "password": "securepass1"},
            )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_upstream_error_returns_400(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.sign_up.side_effect = Exception("unexpected error")
            resp = client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "securepass1"},
            )
        assert resp.status_code == 400

    def test_invalid_email_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "securepass1"},
        )
        assert resp.status_code == 422

    def test_short_password_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "short"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_success_returns_200_with_tokens(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.sign_in_with_password.return_value = (
                _mock_supabase_auth_resp()
            )
            resp = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["id"] == "user-abc"

    def test_wrong_credentials_returns_401(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.sign_in_with_password.side_effect = Exception(
                "invalid login credentials"
            )
            resp = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "wrongpass1"},
            )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    def test_invalid_email_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/login",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    @pytest.fixture(autouse=True)
    def override_auth(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        yield
        app.dependency_overrides.clear()

    def test_success_returns_204_and_calls_sign_out_with_jwt(
        self, client: TestClient
    ) -> None:
        with patch("routers.auth.get_db") as mock_db:
            resp = client.post(
                "/auth/logout", headers={"Authorization": "Bearer jwt-token"}
            )
        assert resp.status_code == 204
        mock_db.return_value.auth.admin.sign_out.assert_called_once_with(
            MOCK_USER["token"]
        )

    def test_sign_out_failure_is_non_fatal_returns_204(
        self, client: TestClient
    ) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.admin.sign_out.side_effect = Exception(
                "upstream error"
            )
            resp = client.post(
                "/auth/logout", headers={"Authorization": "Bearer jwt-token"}
            )
        assert resp.status_code == 204


class TestLogoutUnauthenticated:
    def test_missing_auth_header_returns_401(self, client: TestClient) -> None:
        resp = client.post("/auth/logout")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_success_returns_new_tokens(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.refresh_session.return_value = (
                _mock_supabase_auth_resp("new_access", "new_refresh")
            )
            resp = client.post(
                "/auth/refresh", json={"refresh_token": "old_refresh_token"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new_access"
        assert data["refresh_token"] == "new_refresh"

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        with patch("routers.auth.get_db") as mock_db:
            mock_db.return_value.auth.refresh_session.side_effect = Exception(
                "token expired"
            )
            resp = client.post(
                "/auth/refresh", json={"refresh_token": "expired_token"}
            )
        assert resp.status_code == 401
        assert "Invalid or expired refresh token" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    @pytest.fixture(autouse=True)
    def override_auth(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: MOCK_USER
        yield
        app.dependency_overrides.clear()

    def test_returns_user_id_and_email(self, client: TestClient) -> None:
        resp = client.get("/auth/me", headers={"Authorization": "Bearer jwt-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == MOCK_USER["id"]
        assert data["email"] == MOCK_USER["email"]


class TestMeUnauthenticated:
    def test_missing_auth_header_returns_401(self, client: TestClient) -> None:
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client: TestClient) -> None:
        with patch("core.dependencies.get_db") as mock_db:
            mock_db.return_value.auth.get_user.side_effect = Exception("JWT expired")
            resp = client.get("/auth/me", headers={"Authorization": "Bearer expired.jwt.token"})
        assert resp.status_code == 401
