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


class TestAcceptPick:
    def test_accept_pick_rejects_duplicate_pick_number(
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
            "platform": "espn",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 10, "cursor": None},
            "accepted_picks": [],
        }

        with pytest.raises(ValueError, match="already processed"):
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=10, now=now)

        mock_repo.update_session_progress.assert_not_called()

    def test_accept_pick_rejects_out_of_turn_pick_number(
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
            "platform": "espn",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 10, "cursor": None},
            "accepted_picks": [],
        }

        with pytest.raises(ValueError, match="out of turn"):
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=13, now=now)

        mock_repo.update_session_progress.assert_not_called()

    def test_accept_pick_updates_sync_state_and_accepted_picks(
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
            "platform": "espn",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 10, "cursor": "pk_10"},
            "accepted_picks": [
                {
                    "pick_number": 10,
                    "platform": "espn",
                    "ingestion_mode": "manual",
                    "timestamp": "2026-04-11T10:00:00+00:00",
                    "player_lookup": {"external_pick_number": 10},
                }
            ],
        }

        result = service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=11, now=now)

        assert result["sync_state"]["last_processed_pick"] == 11
        assert result["accepted_pick"]["pick_number"] == 11
        assert result["accepted_pick"]["platform"] == "espn"
        assert result["accepted_pick"]["ingestion_mode"] == "manual"

        update_kwargs = mock_repo.update_session_progress.call_args.kwargs
        assert update_kwargs["session_id"] == "ses_1"
        assert update_kwargs["user_id"] == "usr_1"
        assert update_kwargs["sync_state"]["last_processed_pick"] == 11
        assert update_kwargs["accepted_picks"][-1]["pick_number"] == 11


class TestObservability:
    def test_attach_socket_emits_log_and_counter(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 12, "cursor": "pk_12"},
        }

        with caplog.at_level("INFO"):
            payload = service.attach_socket(session_id="ses_1", user_id="usr_1", now=now)

        assert payload["last_processed_pick"] == 12
        counters = service.get_observability_counters()
        assert counters["socket_attach"] == 1
        assert "draft_session.socket_attach" in caplog.text
        record = next(r for r in caplog.records if r.message == "draft_session.socket_attach")
        assert record.session_id == "ses_1"
        assert record.user_id == "usr_1"
        assert record.sync_health == "healthy"
        assert record.last_processed_pick == 12

    def test_reconnect_sync_state_emits_log_and_counter(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {
                "sync_health": "degraded",
                "last_processed_pick": 12,
                "cursor": "pk_12",
            },
        }

        with caplog.at_level("INFO"):
            payload = service.reconnect_sync_state(session_id="ses_1", user_id="usr_1", now=now)

        assert payload["last_processed_pick"] == 12
        counters = service.get_observability_counters()
        assert counters["socket_reconnect"] == 1
        assert "draft_session.socket_reconnect" in caplog.text
        record = next(r for r in caplog.records if r.message == "draft_session.socket_reconnect")
        assert record.session_id == "ses_1"
        assert record.user_id == "usr_1"
        assert record.sync_health == "degraded"
        assert record.last_processed_pick == 12

    def test_accept_pick_in_manual_mode_tracks_fallback_counter(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "platform": "espn",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 4, "cursor": "pk_4"},
            "accepted_picks": [],
        }

        with caplog.at_level("INFO"):
            result = service.accept_pick(
                session_id="ses_1", user_id="usr_1", pick_number=5, now=now
            )

        assert result["accepted_pick"]["ingestion_mode"] == "manual"
        counters = service.get_observability_counters()
        assert counters["manual_fallback"] == 1
        assert "draft_session.manual_fallback" in caplog.text
        record = next(r for r in caplog.records if r.message == "draft_session.manual_fallback")
        assert record.session_id == "ses_1"
        assert record.user_id == "usr_1"
        assert record.pick_number == 5

    def test_accept_pick_from_unhealthy_state_tracks_sync_recovery(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        now = datetime.now(UTC)
        mock_sub_repo.is_active.return_value = True
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "platform": "espn",
            "sync_state": {
                "sync_health": "degraded",
                "last_processed_pick": 20,
                "cursor": "pk_20",
            },
            "accepted_picks": [],
        }

        with caplog.at_level("INFO"):
            result = service.accept_pick(
                session_id="ses_1",
                user_id="usr_1",
                pick_number=21,
                now=now,
                ingestion_mode="socket",
            )

        assert result["sync_state"]["sync_health"] == "healthy"
        counters = service.get_observability_counters()
        assert counters["sync_recovery"] == 1
        assert counters["manual_fallback"] == 0
        assert "draft_session.sync_recovery" in caplog.text
        record = next(r for r in caplog.records if r.message == "draft_session.sync_recovery")
        assert record.session_id == "ses_1"
        assert record.user_id == "usr_1"
        assert record.pick_number == 21
