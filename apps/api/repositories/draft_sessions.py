"""Repository for authoritative live draft sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class DraftSessionRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def create_session(self, payload: dict[str, Any]) -> None:
        self._db.table("draft_sessions").insert(payload).execute()

    def get_active_session(
        self,
        user_id: str,
        *,
        active_after: datetime | None = None,
    ) -> dict[str, Any] | None:
        query = (
            self._db.table("draft_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
        )
        if active_after is not None:
            query = query.gte("last_heartbeat_at", active_after.isoformat())
        result = query.maybe_single().execute()
        return result.data

    def get_session_by_id(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Fetch a session regardless of status — used to distinguish terminal from not-found."""
        result = (
            self._db.table("draft_sessions")
            .select("*")
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data

    def resume_session(self, *, session_id: str, user_id: str, now: datetime) -> None:
        now_iso = now.astimezone(UTC).isoformat()
        (
            self._db.table("draft_sessions")
            .update(
                {
                    "recovered_at": now_iso,
                    "last_heartbeat_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

    def touch_heartbeat(self, *, session_id: str, user_id: str, now: datetime) -> None:
        now_iso = now.astimezone(UTC).isoformat()
        (
            self._db.table("draft_sessions")
            .update(
                {
                    "last_heartbeat_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

    def end_session(self, *, session_id: str, user_id: str, now: datetime) -> None:
        now_iso = now.astimezone(UTC).isoformat()
        (
            self._db.table("draft_sessions")
            .update(
                {
                    "status": "ended",
                    "completion_reason": "user_ended",
                    "completed_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .execute()
        )

    def update_session_progress(
        self,
        *,
        session_id: str,
        user_id: str,
        sync_state: dict[str, Any],
        accepted_picks: list[dict[str, Any]],
        now: datetime,
    ) -> None:
        now_iso = now.astimezone(UTC).isoformat()
        (
            self._db.table("draft_sessions")
            .update(
                {
                    "sync_state": sync_state,
                    "accepted_picks": accepted_picks,
                    "last_heartbeat_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

    def expire_inactive_sessions(self, cutoff: datetime) -> int:
        now_iso = datetime.now(UTC).isoformat()
        result = (
            self._db.table("draft_sessions")
            .update(
                {
                    "status": "expired",
                    "completion_reason": "inactivity_expired",
                    "completed_at": now_iso,
                    "updated_at": now_iso,
                }
            )
            .eq("status", "active")
            .lt("last_heartbeat_at", cutoff.astimezone(UTC).isoformat())
            .execute()
        )
        return len(result.data or [])
