"""Unit tests for DraftSessionService authority rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.draft_sessions import DraftSessionService


@pytest.fixture
def mock_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_repo: MagicMock, mock_sub_repo: MagicMock) -> DraftSessionService:
    return DraftSessionService(
        draft_session_repo=mock_repo,
        subscription_repo=mock_sub_repo,
        inactivity_timeout=timedelta(minutes=15),
    )


class TestStartSession:
    def test_requires_active_entitlement(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="active draft pass"):
            service.start_session(user_id="usr_1", platform="espn", now=datetime.now(UTC))

        mock_repo.create_session.assert_not_called()

    def test_returns_existing_active_session_without_creating_new(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        existing = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = existing

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result == existing
        mock_repo.create_session.assert_not_called()

    def test_creates_new_session_when_none_active(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = None

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result["user_id"] == "usr_1"
        assert result["platform"] == "espn"
        assert result["status"] == "active"
        assert result["sync_state"]["sync_health"] == "healthy"
        mock_repo.create_session.assert_called_once()


class TestResumeSession:
    def test_resume_requires_active_entitlement(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="active draft pass"):
            service.resume_session(
                session_id="ses_1",
                user_id="usr_1",
                now=datetime.now(UTC),
            )

        mock_repo.resume_session.assert_not_called()

    def test_resume_rejects_missing_or_non_owned_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_other",
            "user_id": "usr_1",
            "status": "active",
        }

        with pytest.raises(LookupError, match="session not found"):
            service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        mock_repo.resume_session.assert_not_called()

    def test_resume_updates_heartbeat_and_returns_active_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        active = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = active

        result = service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        assert result == active
        mock_repo.resume_session.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )


class TestInactivitySweep:
    def test_expires_inactive_sessions_at_timeout_boundary(
        self, service: DraftSessionService, mock_repo: MagicMock
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.expire_inactive_sessions.return_value = 2

        expired = service.expire_inactive_sessions(now)

        assert expired == 2
        mock_repo.expire_inactive_sessions.assert_called_once_with(now - timedelta(minutes=15))


class TestEndAndSyncState:
    def test_end_session_requires_matching_active_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_other",
            "user_id": "usr_1",
            "status": "active",
        }

        with pytest.raises(LookupError, match="session not found"):
            service.end_session(session_id="ses_1", user_id="usr_1", now=now)

        mock_repo.end_session.assert_not_called()

    def test_end_session_marks_matching_session_ended(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
        }

        service.end_session(session_id="ses_1", user_id="usr_1", now=now)

        mock_repo.end_session.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )

    def test_get_sync_state_returns_authoritative_payload(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 14},
        }

        sync_state = service.get_sync_state(session_id="ses_1", user_id="usr_1", now=now)

        assert sync_state["sync_health"] == "healthy"
        assert sync_state["last_processed_pick"] == 14

    def test_get_sync_state_raises_when_session_missing(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = None

        with pytest.raises(LookupError, match="session not found"):
            service.get_sync_state(session_id="ses_1", user_id="usr_1", now=now)
