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
