"""Authority rules for live draft sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from repositories.draft_sessions import DraftSessionRepository
from repositories.subscriptions import SubscriptionRepository


class DraftSessionService:
    def __init__(
        self,
        *,
        draft_session_repo: DraftSessionRepository,
        subscription_repo: SubscriptionRepository,
        inactivity_timeout: timedelta,
    ) -> None:
        self._draft_session_repo = draft_session_repo
        self._subscription_repo = subscription_repo
        self._inactivity_timeout = inactivity_timeout

    def start_session(self, *, user_id: str, platform: str, now: datetime) -> dict:
        self._require_active_pass(user_id)

        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is not None:
            return active

        now_iso = now.astimezone(UTC).isoformat()
        payload = {
            "session_id": f"ses_{uuid4().hex}",
            "user_id": user_id,
            "platform": platform,
            "status": "active",
            "sync_state": {
                "last_processed_pick": None,
                "sync_health": "healthy",
                "cursor": None,
            },
            "accepted_picks": [],
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat_at": now_iso,
        }
        self._draft_session_repo.create_session(payload)
        return payload

    def resume_session(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        self._require_active_pass(user_id)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            raise LookupError("active session not found for user")

        self._draft_session_repo.resume_session(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )
        return active

    def expire_inactive_sessions(self, now: datetime) -> int:
        cutoff = now - self._inactivity_timeout
        return self._draft_session_repo.expire_inactive_sessions(cutoff)

    def end_session(self, *, session_id: str, user_id: str, now: datetime) -> None:
        self._require_active_pass(user_id)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            raise LookupError("active session not found for user")
        self._draft_session_repo.end_session(
            session_id=session_id,
            user_id=user_id,
            now=now,
        )

    def get_sync_state(self, *, session_id: str, user_id: str, now: datetime) -> dict:
        self._require_active_pass(user_id)
        active = self._draft_session_repo.get_active_session(
            user_id,
            active_after=now - self._inactivity_timeout,
        )
        if active is None or active.get("session_id") != session_id:
            raise LookupError("active session not found for user")
        return active.get("sync_state", {})

    def _require_active_pass(self, user_id: str) -> None:
        if not self._subscription_repo.is_active(user_id):
            raise PermissionError("active draft pass required")
