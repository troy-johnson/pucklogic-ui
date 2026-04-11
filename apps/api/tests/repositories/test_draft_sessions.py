"""Unit tests for DraftSessionRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from repositories.draft_sessions import DraftSessionRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> DraftSessionRepository:
    return DraftSessionRepository(mock_db)


class TestDraftSessionRepositoryLifecycle:
    def test_create_session_inserts_payload(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        payload = {
            "session_id": "ses_1",
            "user_id": "usr_1",
            "platform": "espn",
            "status": "active",
        }

        repo.create_session(payload)

        mock_db.table.assert_called_with("draft_sessions")
        mock_db.table.return_value.insert.assert_called_once_with(payload)
        mock_db.table.return_value.insert.return_value.execute.assert_called_once()

    def test_get_active_session_queries_active_by_user(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        table = mock_db.table.return_value
        query = table.select.return_value.eq.return_value.eq.return_value
        chain = query.maybe_single.return_value.execute.return_value
        chain.data = {"session_id": "ses_1", "status": "active"}

        row = repo.get_active_session("usr_1")

        assert row == {"session_id": "ses_1", "status": "active"}
        mock_db.table.return_value.select.return_value.eq.assert_any_call("user_id", "usr_1")
        mock_db.table.return_value.select.return_value.eq.return_value.eq.assert_any_call(
            "status", "active"
        )

    def test_resume_session_sets_recovered_and_heartbeat(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        now = datetime.now(UTC)

        repo.resume_session(session_id="ses_1", user_id="usr_1", now=now)

        update_call = (
            mock_db.table.return_value.update.call_args.args[0]
            if mock_db.table.return_value.update.call_args.args
            else mock_db.table.return_value.update.call_args.kwargs.get("json", {})
        )
        assert update_call["recovered_at"] == now.isoformat()
        assert update_call["last_heartbeat_at"] == now.isoformat()

    def test_end_session_marks_status_ended(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        now = datetime.now(UTC)

        repo.end_session(session_id="ses_1", user_id="usr_1", now=now)

        update_call = (
            mock_db.table.return_value.update.call_args.args[0]
            if mock_db.table.return_value.update.call_args.args
            else mock_db.table.return_value.update.call_args.kwargs.get("json", {})
        )
        assert update_call["status"] == "ended"
        assert update_call["updated_at"] == now.isoformat()

    def test_update_session_progress_updates_sync_state_and_picks(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        now = datetime.now(UTC)
        sync_state = {"sync_health": "healthy", "last_processed_pick": 11, "cursor": "pk_11"}
        accepted_picks = [
            {
                "pick_number": 11,
                "platform": "espn",
                "ingestion_mode": "manual",
                "timestamp": now.isoformat(),
                "player_lookup": {"external_pick_number": 11},
            }
        ]

        repo.update_session_progress(
            session_id="ses_1",
            user_id="usr_1",
            sync_state=sync_state,
            accepted_picks=accepted_picks,
            now=now,
        )

        update_call = (
            mock_db.table.return_value.update.call_args.args[0]
            if mock_db.table.return_value.update.call_args.args
            else mock_db.table.return_value.update.call_args.kwargs.get("json", {})
        )
        assert update_call["sync_state"] == sync_state
        assert update_call["accepted_picks"] == accepted_picks
        assert update_call["last_heartbeat_at"] == now.isoformat()
        assert update_call["updated_at"] == now.isoformat()


class TestDraftSessionRepositoryExpiry:
    def test_get_active_session_with_cutoff_filters_heartbeat(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        cutoff = datetime(2026, 4, 11, tzinfo=UTC)
        table = mock_db.table.return_value
        query = table.select.return_value.eq.return_value.eq.return_value
        chain = query.gte.return_value.maybe_single.return_value.execute.return_value
        chain.data = {"session_id": "ses_1", "status": "active"}

        row = repo.get_active_session("usr_1", active_after=cutoff)

        assert row == {"session_id": "ses_1", "status": "active"}
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.assert_called_once_with(
            "last_heartbeat_at", cutoff.isoformat()
        )

    def test_expire_inactive_sessions_marks_active_rows_expired(
        self, repo: DraftSessionRepository, mock_db: MagicMock
    ) -> None:
        cutoff = datetime(2026, 4, 11, tzinfo=UTC)
        table = mock_db.table.return_value
        result = table.update.return_value.eq.return_value.lt.return_value.execute.return_value
        result.data = [{"session_id": "ses_1"}, {"session_id": "ses_2"}]

        expired_count = repo.expire_inactive_sessions(cutoff)

        update_call = (
            mock_db.table.return_value.update.call_args.args[0]
            if mock_db.table.return_value.update.call_args.args
            else mock_db.table.return_value.update.call_args.kwargs.get("json", {})
        )
        assert update_call["status"] == "expired"
        assert "updated_at" in update_call
        assert expired_count == 2
