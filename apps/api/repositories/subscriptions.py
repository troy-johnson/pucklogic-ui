"""Repository for the `subscriptions` table."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


class SubscriptionRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def upsert(self, user_id: str, plan: str) -> None:
        """Insert or update the subscription row for *user_id*."""
        self._db.table("subscriptions").upsert(
            {"user_id": user_id, "plan": plan},
            on_conflict="user_id",
        ).execute()

    def get_subscription_id(self, user_id: str) -> str | None:
        """Return the id of the active subscription row for *user_id*, or None."""
        from datetime import UTC, datetime

        result = (
            self._db.table("subscriptions")
            .select("id, expires_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return None
        expires_at = result.data.get("expires_at")
        if expires_at is not None and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            return None
        return result.data.get("id")

    def is_active(self, user_id: str) -> bool:
        """Return True if user_id has an active, non-expired subscription."""
        from datetime import UTC, datetime

        result = (
            self._db.table("subscriptions")
            .select("status, expires_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return False
        expires_at = result.data.get("expires_at")
        if expires_at is None:
            return True
        return datetime.fromisoformat(expires_at) > datetime.now(UTC)
