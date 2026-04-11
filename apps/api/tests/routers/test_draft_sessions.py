"""Integration tests for live draft session router."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_current_user, get_draft_session_service
from main import app

MOCK_USER = {"id": "usr_123", "email": "user@example.com"}


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def override_deps(mock_service: MagicMock) -> None:
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_draft_session_service] = lambda: mock_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestStartDraftSession:
    def test_start_returns_200_with_session_payload(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        response = client.post("/draft-sessions/start", json={"platform": "espn"})

        assert response.status_code == 200
        assert response.json()["session_id"] == "ses_1"
        assert response.json()["platform"] == "espn"

    def test_start_uses_authenticated_user_id(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        client.post("/draft-sessions/start", json={"platform": "espn"})

        kwargs = mock_service.start_session.call_args.kwargs
        assert kwargs["user_id"] == "usr_123"
        assert kwargs["platform"] == "espn"

    def test_start_returns_403_without_entitlement(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.start_session.side_effect = PermissionError("active draft pass required")

        response = client.post("/draft-sessions/start", json={"platform": "espn"})

        assert response.status_code == 403


class TestResumeDraftSession:
    def test_resume_returns_200(self, client: TestClient, mock_service: MagicMock) -> None:
        mock_service.resume_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_123",
            "platform": "espn",
            "status": "active",
            "sync_state": {"sync_health": "healthy"},
        }

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 200
        assert response.json()["session_id"] == "ses_1"

    def test_resume_returns_404_when_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.resume_session.side_effect = LookupError("active session not found for user")

        response = client.post("/draft-sessions/ses_1/resume")

        assert response.status_code == 404


class TestEndDraftSession:
    def test_end_returns_204(self, client: TestClient, mock_service: MagicMock) -> None:
        response = client.post("/draft-sessions/ses_1/end")

        assert response.status_code == 204
        mock_service.end_session.assert_called_once()


class TestSyncState:
    def test_get_sync_state_returns_payload(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.get_sync_state.return_value = {
            "sync_health": "healthy",
            "last_processed_pick": 18,
        }

        response = client.get("/draft-sessions/ses_1/sync-state")

        assert response.status_code == 200
        assert response.json()["sync_health"] == "healthy"

    def test_get_sync_state_returns_404_when_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        mock_service.get_sync_state.side_effect = LookupError("active session not found for user")

        response = client.get("/draft-sessions/ses_1/sync-state")

        assert response.status_code == 404
