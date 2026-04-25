"""Unit tests for DraftSessionService authority rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.draft_sessions import DraftSessionService, TerminalSessionError


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
        mock_repo.get_active_session.return_value = None
        mock_sub_repo.consume_draft_pass.side_effect = PermissionError("active draft pass required")

        with pytest.raises(PermissionError, match="active draft pass"):
            service.start_session(user_id="usr_1", platform="espn", now=datetime.now(UTC))

        mock_repo.create_session.assert_not_called()

    def test_rejects_expired_subscription_even_with_positive_pass_balance(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        mock_repo.get_active_session.return_value = None
        mock_sub_repo.consume_draft_pass.side_effect = PermissionError("active draft pass required")

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
        mock_repo.get_active_session.return_value = existing

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result == existing
        mock_repo.create_session.assert_not_called()
        mock_sub_repo.consume_draft_pass.assert_not_called()

    def test_creates_new_session_when_none_active(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result["user_id"] == "usr_1"
        assert result["platform"] == "espn"
        assert result["status"] == "active"
        assert result["entitlement_ref"] == "sub_abc123"
        assert result["sync_state"]["sync_health"] == "healthy"
        mock_repo.create_session.assert_called_once()
        mock_sub_repo.consume_draft_pass.assert_called_once_with("usr_1", now=now)

    def test_start_session_expires_inactive_rows_before_lookup(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"

        service.start_session(user_id="usr_1", platform="espn", now=now)

        cutoff = now - timedelta(minutes=15)
        mock_repo.expire_inactive_sessions.assert_called_once_with(cutoff)

    def test_start_session_stores_entitlement_ref(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"

        service.start_session(user_id="usr_1", platform="espn", now=now)

        payload = mock_repo.create_session.call_args.args[0]
        assert payload["entitlement_ref"] == "sub_abc123"

    def test_restores_pass_if_session_create_fails(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.side_effect = [None, None]
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"
        mock_repo.create_session.side_effect = RuntimeError("insert failed")

        with pytest.raises(RuntimeError, match="insert failed"):
            service.start_session(user_id="usr_1", platform="espn", now=now)

        mock_sub_repo.restore_draft_pass.assert_called_once_with("sub_abc123")

    def test_returns_raced_active_session_when_create_loses_race(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """If create_session fails after consume (uniqueness violation) and a raced session
        exists, restore the pass and return the winner's session rather than raising."""
        now = datetime.now(UTC)
        raced_active = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        mock_repo.get_active_session.side_effect = [None, raced_active]
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"
        mock_repo.create_session.side_effect = RuntimeError("unique constraint violation")

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result == raced_active
        mock_sub_repo.restore_draft_pass.assert_called_once_with("sub_abc123")

    def test_does_not_restore_pass_when_create_error_arrives_after_own_insert_commits(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.side_effect = [
            None,
            {
                "session_id": "ses_committed",
                "user_id": "usr_1",
                "status": "active",
                "entitlement_ref": "sub_abc123",
            },
        ]
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"
        mock_repo.create_session.side_effect = RuntimeError("post-commit timeout")

        original_uuid4 = DraftSessionService.start_session.__globals__["uuid4"]
        DraftSessionService.start_session.__globals__["uuid4"] = lambda: type(
            "FixedUuid", (), {"hex": "committed"}
        )()
        try:
            result = service.start_session(user_id="usr_1", platform="espn", now=now)
        finally:
            DraftSessionService.start_session.__globals__["uuid4"] = original_uuid4

        assert result["session_id"] == "ses_committed"
        mock_sub_repo.restore_draft_pass.assert_not_called()


class TestPassConsumptionInvariants:
    def test_start_does_not_consume_pass_on_existing_active_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """Returning an existing session must not check balance or deduct a pass."""
        now = datetime.now(UTC)
        existing = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "entitlement_ref": "sub_old",
        }
        mock_repo.get_active_session.return_value = existing

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result is existing
        mock_repo.create_session.assert_not_called()
        mock_sub_repo.consume_draft_pass.assert_not_called()

    def test_reconnect_does_not_consume_pass(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """resume_session must not check balance or deduct — reconnect never re-consumes."""
        now = datetime.now(UTC)
        active = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        resumed = {**active, "last_heartbeat_at": now.isoformat()}
        mock_repo.get_active_session.side_effect = [active, resumed]

        service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        mock_sub_repo.consume_draft_pass.assert_not_called()
        mock_repo.create_session.assert_not_called()

    def test_same_pass_cannot_back_two_active_sessions(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """Active session for this user: start returns it without creating a second."""
        now = datetime.now(UTC)
        existing = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "entitlement_ref": "sub_abc123",
        }
        mock_repo.get_active_session.return_value = existing

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result["session_id"] == "ses_1"
        mock_repo.create_session.assert_not_called()
        mock_sub_repo.consume_draft_pass.assert_not_called()


class TestSecondStartAntiAbuse:
    def test_second_start_does_not_create_concurrent_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """A second start attempt while a session is active returns the existing session."""
        now = datetime.now(UTC)
        existing = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        mock_repo.get_active_session.return_value = existing

        first = service.start_session(user_id="usr_1", platform="espn", now=now)
        second = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert first["session_id"] == second["session_id"] == "ses_1"
        mock_repo.create_session.assert_not_called()
        mock_sub_repo.consume_draft_pass.assert_not_called()

    def test_concurrent_start_never_calls_create_session_twice(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """Even repeated start calls must not result in more than one create_session call."""
        now = datetime.now(UTC)
        mock_sub_repo.consume_draft_pass.return_value = "sub_abc123"
        # First call: no active session → creates one. Second call: session exists → returns it.
        mock_repo.get_active_session.side_effect = [
            None,
            {"session_id": "ses_1", "status": "active"},
        ]

        service.start_session(user_id="usr_1", platform="espn", now=now)
        service.start_session(user_id="usr_1", platform="espn", now=now)

        mock_repo.create_session.assert_called_once()
        mock_sub_repo.consume_draft_pass.assert_called_once_with("usr_1", now=now)

    def test_returns_raced_active_session_when_atomic_consume_loses_race(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        raced_active = {"session_id": "ses_1", "user_id": "usr_1", "status": "active"}
        mock_repo.get_active_session.side_effect = [None, raced_active]
        mock_sub_repo.consume_draft_pass.side_effect = PermissionError("active draft pass required")

        result = service.start_session(user_id="usr_1", platform="espn", now=now)

        assert result == raced_active
        mock_repo.create_session.assert_not_called()


class TestTerminalSessionDenial:
    def test_resume_session_raises_for_user_ended_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """Reconnecting to an explicitly ended session must raise a closed-session error."""
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "ended",
            "completion_reason": "user_ended",
        }

        with pytest.raises(LookupError, match="closed"):
            service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

    def test_resume_session_raises_for_inactivity_expired_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """Reconnecting to an inactivity-expired session must raise a closed-session error."""
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "expired",
            "completion_reason": "inactivity_expired",
        }

        with pytest.raises(LookupError, match="closed"):
            service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

    def test_attach_socket_raises_for_terminal_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        """WS attach to a terminal session must raise a closed-session error."""
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "ended",
            "completion_reason": "user_ended",
        }

        with pytest.raises(LookupError, match="closed"):
            service.attach_socket(session_id="ses_1", user_id="usr_1", now=now)


class TestResumeSession:
    def test_resume_rejects_missing_or_non_owned_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
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
        resumed = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "last_heartbeat_at": now.isoformat(),
        }
        mock_repo.get_active_session.side_effect = [active, resumed]
        mock_sub_repo.is_active.return_value = True

        result = service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        assert result == resumed
        mock_repo.resume_session.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )

    def test_resume_raises_when_entitlement_inactive(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
        }
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="active subscription required"):
            service.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        mock_repo.resume_session.assert_not_called()


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

    def test_end_session_allows_cleanup_without_active_entitlement(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)

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

        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 14},
        }

        sync_state = service.get_sync_state(session_id="ses_1", user_id="usr_1", now=now)

        assert sync_state["sync_health"] == "healthy"
        assert sync_state["last_processed_pick"] == 14

    def test_get_sync_state_raises_when_entitlement_inactive(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 14},
        }
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="active subscription required"):
            service.get_sync_state(session_id="ses_1", user_id="usr_1", now=now)


class TestReconnectSyncState:
    def test_reconnect_sync_state_returns_sync_state_when_entitled(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 14},
        }
        mock_sub_repo.is_active.return_value = True

        sync_state = service.reconnect_sync_state(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )

        assert sync_state == {"sync_health": "healthy", "last_processed_pick": 14}
        mock_repo.touch_heartbeat.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )

    def test_reconnect_sync_state_raises_when_entitlement_inactive(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 14},
        }
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="active subscription required"):
            service.reconnect_sync_state(session_id="ses_1", user_id="usr_1", now=now)

    def test_get_sync_state_raises_when_session_missing(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)

        mock_repo.get_active_session.return_value = None

        with pytest.raises(LookupError, match="session not found"):
            service.get_sync_state(session_id="ses_1", user_id="usr_1", now=now)

    def test_reconnect_sync_state_calls_expire_inactive_sessions(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {},
        }
        mock_sub_repo.is_active.return_value = True

        service.reconnect_sync_state(session_id="ses_1", user_id="usr_1", now=now)

        mock_repo.expire_inactive_sessions.assert_called_once()


class TestAcceptPick:
    def test_accept_pick_rejects_duplicate_pick_number(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)

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

        result = service.accept_pick(
            session_id="ses_1",
            user_id="usr_1",
            pick_number=11,
            now=now,
            player_id="8478402",
            player_name="Connor McDavid",
            player_lookup={"espn_player_id": "8478402"},
        )

        assert result["sync_state"]["last_processed_pick"] == 11
        assert result["accepted_pick"]["pick_number"] == 11
        assert result["accepted_pick"]["platform"] == "espn"
        assert result["accepted_pick"]["ingestion_mode"] == "manual"
        assert result["accepted_pick"]["player_id"] == "8478402"
        assert result["accepted_pick"]["player_name"] == "Connor McDavid"
        assert result["accepted_pick"]["player_lookup"] == {"espn_player_id": "8478402"}

        update_kwargs = mock_repo.update_session_progress.call_args.kwargs
        assert update_kwargs["session_id"] == "ses_1"
        assert update_kwargs["user_id"] == "usr_1"
        assert update_kwargs["sync_state"]["last_processed_pick"] == 11
        assert update_kwargs["accepted_picks"][-1]["pick_number"] == 11


class TestAcceptPickSubscriptionGate:
    def test_accept_pick_raises_permission_error_when_subscription_inactive(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "platform": "espn",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 10, "cursor": None},
            "accepted_picks": [],
        }
        mock_sub_repo.is_active.return_value = False

        with pytest.raises(PermissionError, match="subscription"):
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=11, now=now)

        mock_repo.update_session_progress.assert_not_called()


class TestAcceptPickTerminalSession:
    def test_accept_pick_raises_terminal_error_for_ended_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "ended",
            "completion_reason": "user_ended",
        }

        with pytest.raises(TerminalSessionError, match="closed"):
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=1, now=now)

        mock_repo.update_session_progress.assert_not_called()

    def test_accept_pick_raises_terminal_error_for_expired_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "expired",
            "completion_reason": "inactivity_expired",
        }

        with pytest.raises(TerminalSessionError, match="closed"):
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=1, now=now)

        mock_repo.update_session_progress.assert_not_called()

    def test_accept_pick_raises_generic_lookup_for_truly_missing_session(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        mock_repo.get_active_session.return_value = None
        mock_repo.get_session_by_id.return_value = None

        with pytest.raises(LookupError, match="session not found") as exc_info:
            service.accept_pick(session_id="ses_1", user_id="usr_1", pick_number=1, now=now)

        assert not isinstance(exc_info.value, TerminalSessionError)
        mock_repo.update_session_progress.assert_not_called()


class TestObservability:
    def test_attach_socket_emits_log_and_counter(
        self,
        service: DraftSessionService,
        mock_repo: MagicMock,
        mock_sub_repo: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        now = datetime.now(UTC)

        mock_repo.get_active_session.return_value = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "status": "active",
            "sync_state": {"sync_health": "healthy", "last_processed_pick": 12, "cursor": "pk_12"},
        }

        with caplog.at_level("INFO"):
            payload = service.attach_socket(session_id="ses_1", user_id="usr_1", now=now)

        assert payload["last_processed_pick"] == 12
        mock_repo.touch_heartbeat.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )
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
        mock_repo.touch_heartbeat.assert_called_once_with(
            session_id="ses_1",
            user_id="usr_1",
            now=now,
        )
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
                ingestion_mode="auto",
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
